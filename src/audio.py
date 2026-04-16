# Module: audio
# Procedural audio manager. No external assets — all sfx and the menu music
# are synthesised as WAV files into ./assets/audio/ on first run and cached
# for subsequent launches. Volumes are persisted to settings.json.
#
# Public API:
#   init()             — boot pygame mixer + generate assets if missing
#   play_sfx(name)     — fire-and-forget sound effect
#   play_music(name)   — looping background music
#   stop_music()
#   set_master(v), set_music(v), set_sfx(v)   # 0.0..1.0
#   get_volumes()      → dict
# SFX names: 'click', 'select', 'musket', 'cannon', 'cavalry', 'victory', 'defeat'
# Music names: 'menu'

import json
import math
import os
import random
import struct
import wave

import pygame

SAMPLE_RATE = 22050
ASSET_DIR   = os.path.join(os.getcwd(), 'assets', 'audio')
SETTINGS    = os.path.join(os.getcwd(), 'settings.json')

_loaded_sfx = {}          # name → pygame.mixer.Sound
_vol = {'master': 0.8, 'music': 0.6, 'sfx': 0.9}
_current_music = None


# ── waveform helpers ───────────────────────────────────────────────────────

def _env(t, dur, attack=0.01, release=0.1):
    """Simple linear ADSR-lite envelope."""
    if t < attack:
        return t / attack
    if t > dur - release:
        return max(0.0, (dur - t) / release)
    return 1.0


def _sine(freq, t):
    return math.sin(2 * math.pi * freq * t)


def _saw(freq, t):
    return 2.0 * (t * freq - math.floor(t * freq + 0.5))


def _saveWav(path, samples):
    """Samples are floats in -1..1; clip + write mono 16-bit PCM."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        buf = bytearray()
        for s in samples:
            v = int(max(-1.0, min(1.0, s)) * 32000)
            buf += struct.pack('<h', v)
        f.writeframes(bytes(buf))


# ── SFX generators ─────────────────────────────────────────────────────────

def _gen_click():
    dur = 0.06
    rng = random.Random(2)
    out = []
    for i in range(int(dur * SAMPLE_RATE)):
        t = i / SAMPLE_RATE
        e = _env(t, dur, 0.001, 0.04)
        out.append((_sine(880, t) * 0.5 + _sine(1760, t) * 0.3) * e)
    return out


def _gen_select():
    dur = 0.12
    out = []
    for i in range(int(dur * SAMPLE_RATE)):
        t = i / SAMPLE_RATE
        e = _env(t, dur, 0.005, 0.07)
        # Two-note blip rising
        freq = 600 + 400 * min(1.0, t / 0.05)
        out.append(_sine(freq, t) * 0.45 * e)
    return out


def _gen_musket():
    """Sharp noise burst with a low-end thump — musket volley."""
    dur = 0.22
    rng = random.Random(3)
    out = []
    for i in range(int(dur * SAMPLE_RATE)):
        t = i / SAMPLE_RATE
        e = _env(t, dur, 0.002, 0.14)
        noise = rng.uniform(-1, 1)
        thump = _sine(90, t) * math.exp(-t * 18) * 0.7
        crack = noise * math.exp(-t * 10) * 0.7
        out.append((crack + thump) * e)
    return out


def _gen_cannon():
    """Deep boom — decaying sine + noise tail."""
    dur = 0.7
    rng = random.Random(4)
    out = []
    for i in range(int(dur * SAMPLE_RATE)):
        t = i / SAMPLE_RATE
        e = _env(t, dur, 0.005, 0.35)
        boom = _sine(55 + 30 * math.exp(-t * 3), t) * math.exp(-t * 4) * 0.9
        rumble = rng.uniform(-1, 1) * math.exp(-t * 6) * 0.4
        out.append((boom + rumble) * e)
    return out


def _gen_cavalry():
    """Brief swoosh + metallic clang."""
    dur = 0.35
    rng = random.Random(5)
    out = []
    for i in range(int(dur * SAMPLE_RATE)):
        t = i / SAMPLE_RATE
        e = _env(t, dur, 0.01, 0.2)
        swoosh = rng.uniform(-1, 1) * math.exp(-t * 8) * 0.4
        clang = _sine(1100, t) * math.exp(-t * 10) * 0.5 \
              + _sine(1620, t) * math.exp(-t * 12) * 0.3
        out.append((swoosh + clang) * e)
    return out


def _gen_victory():
    """Short triumphant chord — major triad arpeggio into hold."""
    dur = 1.4
    out = []
    notes = [(261.6, 0.0), (329.6, 0.12), (392.0, 0.24), (523.2, 0.36)]
    hold_from = 0.55
    for i in range(int(dur * SAMPLE_RATE)):
        t = i / SAMPLE_RATE
        e = _env(t, dur, 0.02, 0.5)
        s = 0.0
        for f, start in notes:
            if t >= start:
                age = t - start
                if t < hold_from or start >= hold_from:
                    s += _sine(f, t) * math.exp(-age * 1.2) * 0.4
                else:
                    s += _sine(f, t) * math.exp(-(t - hold_from) * 0.6) * 0.35
        out.append(s * e)
    return out


def _gen_defeat():
    """Low descending minor chord."""
    dur = 1.8
    out = []
    notes = [(293.6, 0.0), (261.6, 0.3), (196.0, 0.6), (174.6, 0.9)]
    for i in range(int(dur * SAMPLE_RATE)):
        t = i / SAMPLE_RATE
        e = _env(t, dur, 0.02, 0.7)
        s = 0.0
        for f, start in notes:
            if t >= start:
                age = t - start
                s += _sine(f, t) * math.exp(-age * 0.6) * 0.35
        out.append(s * e)
    return out


# ── Menu music ─────────────────────────────────────────────────────────────
# A slow, somber marching theme in D minor. Four-bar chord progression
# (Dm – Bb – F – A) repeated with a simple melody in the second half of each
# loop so it doesn't feel static. 16 seconds long at ~75 BPM.

def _gen_music_menu():
    BPM        = 75
    BEAT       = 60.0 / BPM           # ≈ 0.8 s
    BAR        = BEAT * 4
    LOOP_SECS  = BAR * 4              # 4 bars ≈ 12.8 s

    # Chord progression (root frequency, triad offsets in semitones)
    # Dm, Bb, F, A  — classic mournful progression
    D  = 146.8   # D3
    Bb = 116.5   # A#2
    F  = 87.3    # F2
    A  = 110.0   # A2
    progression = [D, Bb, F, A]

    # Pentatonic-ish melody notes (Hz) played over bars 3-4
    melody = [
        (587.3, 0.0, 0.5),   # D5
        (523.2, 0.6, 0.5),   # C5
        (440.0, 1.2, 0.7),   # A4
        (523.2, 2.2, 0.5),   # C5
        (493.9, 3.0, 0.6),   # B4
        (440.0, 3.8, 1.0),   # A4
    ]

    def _softPluck(freq, t_rel, length):
        """Gentle instrument voice — sine+harmonic with slow decay."""
        if t_rel < 0 or t_rel > length:
            return 0.0
        env = math.exp(-t_rel * 1.2) * _env(t_rel, length, 0.01, 0.3)
        return (_sine(freq, t_rel) + 0.3 * _sine(freq * 2, t_rel)) * env

    total_samples = int(LOOP_SECS * SAMPLE_RATE)
    out = [0.0] * total_samples

    for i in range(total_samples):
        t = i / SAMPLE_RATE

        # ── bass: slow-moving root note, one per bar ──
        bar_idx = int(t / BAR) % 4
        root    = progression[bar_idx]
        bar_t   = t - bar_idx * BAR
        bass = _sine(root, t) * _env(bar_t, BAR, 0.08, 0.3) * 0.28

        # ── pad: triad sustained over each bar ──
        third = root * (2 ** (3 / 12))   # minor third
        fifth = root * (2 ** (7 / 12))
        pad  = (_sine(third * 2, t) + _sine(fifth * 2, t)) \
               * _env(bar_t, BAR, 0.25, 0.4) * 0.06

        s = bass + pad

        # ── melody: only in last two bars of each loop ──
        if t >= BAR * 2:
            m_t = t - BAR * 2
            for freq, start, length in melody:
                s += _softPluck(freq, m_t - start, length) * 0.20

        # Soft master envelope at very start/end for clean loop
        loop_env = _env(t, LOOP_SECS, 0.4, 0.4)
        out[i] = s * loop_env

    return out


# ── asset generation / cache ───────────────────────────────────────────────

_SFX_GENERATORS = {
    'click':    _gen_click,
    'select':   _gen_select,
    'musket':   _gen_musket,
    'cannon':   _gen_cannon,
    'cavalry':  _gen_cavalry,
    'victory':  _gen_victory,
    'defeat':   _gen_defeat,
}
_MUSIC_GENERATORS = {
    'menu': _gen_music_menu,
}


def _ensureAssets():
    """Generate any missing WAV files in ASSET_DIR."""
    os.makedirs(ASSET_DIR, exist_ok=True)
    for name, gen in _SFX_GENERATORS.items():
        path = os.path.join(ASSET_DIR, f'sfx_{name}.wav')
        if not os.path.exists(path):
            _saveWav(path, gen())
    for name, gen in _MUSIC_GENERATORS.items():
        path = os.path.join(ASSET_DIR, f'music_{name}.wav')
        if not os.path.exists(path):
            _saveWav(path, gen())


def _loadSettings():
    try:
        with open(SETTINGS, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return
    for k in ('master', 'music', 'sfx'):
        if k in data:
            _vol[k] = max(0.0, min(1.0, float(data[k])))


def _saveSettings():
    try:
        with open(SETTINGS, 'w', encoding='utf-8') as f:
            json.dump(_vol, f, indent=2)
    except OSError:
        pass


# ── public API ─────────────────────────────────────────────────────────────

_initialised = False

def init():
    global _initialised
    if _initialised:
        return
    try:
        pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 512)
        pygame.mixer.init()
    except pygame.error:
        _initialised = True      # no-op mode if audio device unavailable
        return
    _loadSettings()
    _ensureAssets()
    for name in _SFX_GENERATORS:
        path = os.path.join(ASSET_DIR, f'sfx_{name}.wav')
        try:
            _loaded_sfx[name] = pygame.mixer.Sound(path)
        except pygame.error:
            pass
    _applyMusicVolume()
    _initialised = True


def _applyMusicVolume():
    if pygame.mixer.get_init():
        try:
            pygame.mixer.music.set_volume(_vol['master'] * _vol['music'])
        except pygame.error:
            pass


def play_sfx(name: str):
    snd = _loaded_sfx.get(name)
    if snd is None:
        return
    try:
        snd.set_volume(_vol['master'] * _vol['sfx'])
        snd.play()
    except pygame.error:
        pass


def play_music(name: str = 'menu', loop: bool = True):
    global _current_music
    if not pygame.mixer.get_init():
        return
    path = os.path.join(ASSET_DIR, f'music_{name}.wav')
    if not os.path.exists(path):
        return
    if _current_music == name:
        return
    try:
        pygame.mixer.music.load(path)
        pygame.mixer.music.play(-1 if loop else 0)
        _applyMusicVolume()
        _current_music = name
    except pygame.error:
        pass


def stop_music():
    global _current_music
    if pygame.mixer.get_init():
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass
    _current_music = None


def set_master(v: float):
    _vol['master'] = max(0.0, min(1.0, v)); _applyMusicVolume(); _saveSettings()

def set_music(v: float):
    _vol['music']  = max(0.0, min(1.0, v)); _applyMusicVolume(); _saveSettings()

def set_sfx(v: float):
    _vol['sfx']    = max(0.0, min(1.0, v)); _saveSettings()


def get_volumes() -> dict:
    return dict(_vol)
