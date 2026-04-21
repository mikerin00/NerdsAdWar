# Module: keybinds
# Persists and serves in-game key bindings.
# Saves to keybinds.json next to the exe/script.

import os
import json
import pygame

_FILE = os.path.join(os.getcwd(), 'keybinds.json')

DEFAULTS = {
    'carre':         pygame.K_f,
    'ai_log':        pygame.K_l,
    'start_gevecht': pygame.K_SPACE,
    'ping':          pygame.K_v,
    'battleplan':    pygame.K_b,
    'emote':         pygame.K_t,
    'sel_all':       pygame.K_1,
    'sel_inf':       pygame.K_2,
    'sel_cav':       pygame.K_3,
    'sel_heavy':     pygame.K_4,
    'sel_art':       pygame.K_5,
}

LABELS = {
    'carre':         'Carré formation',
    'ai_log':        'Show AI log',
    'start_gevecht': 'Start battle',
    'ping':          'Send ping',
    'battleplan':    'Battle plan (hold)',
    'emote':         'Emote bar (hold)',
    'sel_all':       'Select all',
    'sel_inf':       'Select infantry',
    'sel_cav':       'Select cavalry',
    'sel_heavy':     'Select heavy infantry',
    'sel_art':       'Select artillery',
}

_current: dict[str, int] = {}


def load() -> None:
    global _current
    _current = dict(DEFAULTS)
    try:
        with open(_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for k, v in data.items():
            if k in DEFAULTS:
                try:
                    _current[k] = int(v)
                except (TypeError, ValueError):
                    pass
    except (OSError, json.JSONDecodeError):
        pass


def save() -> None:
    try:
        with open(_FILE, 'w', encoding='utf-8') as f:
            json.dump(_current, f, indent=2)
    except OSError:
        pass


def get(action: str) -> int:
    return _current.get(action, DEFAULTS[action])


def set_key(action: str, key: int) -> None:
    if action in DEFAULTS:
        _current[action] = key
        save()


def reset() -> None:
    global _current
    _current = dict(DEFAULTS)
    save()


load()
