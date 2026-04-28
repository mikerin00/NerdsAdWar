# Auto-updater — checkt GitHub Releases op een nieuwere versie, downloadt de
# nieuwe exe en herstart het spel. Draait alleen in de gebouwde .exe (frozen).
# In development (gewoon main.py draaien) wordt de check overgeslagen.

import ctypes
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

# ───────── Configuratie ─────────────────────────────────────────────────────
# Vul hier jouw GitHub repo in: "gebruikersnaam/reponaam".
# De tag van elke Release moet exact overeenkomen met src/version.py (bv. v2.9).
# Upload bij elke release BEIDE bestanden: NerdsAdWar.exe + Setup_NerdsAdWar_vX.Y.exe
# De updater downloadt automatisch de NerdsAdWar.exe uit de nieuwste release.
UPDATE_REPO = "mikerin00/NerdsAdWar"
# ────────────────────────────────────────────────────────────────────────────

import threading

_TIMEOUT_CHECK    = 3.0    # seconden voor de API-check
_TIMEOUT_DOWNLOAD = 120.0  # seconden voor de download
_UA = {'User-Agent': 'NerdsAdWar-Updater'}

# ── Asset download helpers ────────────────────────────────────────────────────
# Portraits and game_visuals are not bundled in the exe — fetch missing files
# from the repo on first run (background thread, silent on failure).

_ASSET_BRANCH = 'main'


def _raw_url(repo_path: str) -> str:
    """URL for a raw file in the repo (repo_path uses forward slashes)."""
    return (f"https://raw.githubusercontent.com/{UPDATE_REPO}/"
            f"{_ASSET_BRANCH}/{repo_path}")


def _fetch_file(repo_path: str, local_path: str):
    """Download repo_path → local_path if the local file is missing."""
    if os.path.isfile(local_path):
        return
    try:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        req = urllib.request.Request(_raw_url(repo_path), headers=_UA)
        with urllib.request.urlopen(req, timeout=10.0) as r, \
             open(local_path, 'wb') as f:
            f.write(r.read())
    except Exception:
        pass


# ── Portrait assets ───────────────────────────────────────────────────────────
_PORTRAIT_DIR   = os.path.join('story', 'characters_PNG')
_PORTRAIT_FILES = [
    'hero.png', 'koen.png', 'tim.png', 'mika.png',
    'luuk.png', 'matthijs.png', 'bronisz.png', 'soldaat.png',
]


def downloadPortraits():
    """Download any missing portrait PNGs in a background thread."""
    def _worker():
        for fn in _PORTRAIT_FILES:
            repo  = f"story/characters_PNG/{fn}"
            local = os.path.join(os.getcwd(), _PORTRAIT_DIR, fn)
            _fetch_file(repo, local)
    threading.Thread(target=_worker, daemon=True).start()


# ── Game visuals ──────────────────────────────────────────────────────────────
_GAME_VISUALS_FILES = [
    'game_visuals/menu_background.png',
    'game_visuals/campain/palace.png',
    'game_visuals/campain/borderlands.png',
    'game_visuals/campain/river.png',
    'game_visuals/campain/dry_planes.png',
    'game_visuals/campain/highlands.png',
    'game_visuals/campain/matthijs_fort.png',
    'game_visuals/map_minis/grassland.png',
    'game_visuals/map_minis/forest.png',
    'game_visuals/map_minis/river.png',
    'game_visuals/map_minis/highlands.png',
    'game_visuals/map_minis/dryplanes.png',
    'game_visuals/map_minis/mixed.png',
    'game_visuals/map_minis/wetlands.png',
    'game_visuals/map_minis/twinrivers.png',
    'game_visuals/map_minis/lakelands.png',
]


def downloadGameVisuals():
    """Download any missing game_visuals PNGs in a background thread."""
    def _worker():
        for repo_path in _GAME_VISUALS_FILES:
            local = os.path.join(os.getcwd(), *repo_path.split('/'))
            _fetch_file(repo_path, local)
    threading.Thread(target=_worker, daemon=True).start()


def _parseVersion(v):
    """'v2.8' → (2, 8); ongeldig → (0, 0)."""
    v = v.strip().lstrip('vV')
    try:
        return tuple(int(p) for p in v.split('.'))
    except ValueError:
        return (0, 0)


def _checkRemote(current):
    """Retourneert (tag, download_url) als remote nieuwer is; anders None."""
    if not UPDATE_REPO:
        return None
    api = f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
    try:
        req = urllib.request.Request(api, headers=_UA)
        with urllib.request.urlopen(req, timeout=_TIMEOUT_CHECK) as r:
            data = json.loads(r.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    tag = data.get('tag_name', '')
    if _parseVersion(tag) <= _parseVersion(current):
        return None
    for asset in data.get('assets', []):
        if asset.get('name', '').lower().endswith('.exe'):
            return tag, asset.get('browser_download_url')
    return None


def _askUser(latest, current):
    msg = (f"A new version of Nerds at War is available!\n\n"
           f"   Current:  {current}\n"
           f"   New:      {latest}\n\n"
           f"Download and install now?")
    MB_YESNO = 0x04
    MB_INFO  = 0x40
    IDYES    = 6
    return ctypes.windll.user32.MessageBoxW(
        None, msg, "Update available", MB_YESNO | MB_INFO) == IDYES


def _showError(text):
    ctypes.windll.user32.MessageBoxW(None, text, "Update error", 0x10)


def _download(url, dest):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=_TIMEOUT_DOWNLOAD) as r, \
         open(dest, 'wb') as f:
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            f.write(chunk)


def _getOriginalExe():
    """
    In Nuitka onefile wijst sys.executable naar de geëxtraheerde python.exe,
    niet naar de originele NerdsAdWar.exe. sys.argv[0] bevat wel het juiste pad.
    """
    candidate = os.path.abspath(sys.argv[0])
    if candidate.lower().endswith('.exe') and os.path.isfile(candidate):
        return candidate
    return sys.executable


def _replaceAndRestart(newExeTmp):
    """
    Swap de draaiende exe voor newExeTmp via een losse batch-file.
    Windows laat een draaiende exe niet overschrijven, maar wel hernoemen —
    dus we hernoemen huidige naar .old, zetten nieuwe op zijn plek, herstarten.
    """
    exe  = _getOriginalExe()
    bak  = exe + '.old'
    name = os.path.basename(exe)

    runtime_cache = os.path.join(
        os.environ.get('LOCALAPPDATA', ''), 'NerdsAdWar', 'runtime')

    bat = tempfile.NamedTemporaryFile(
        mode='w', suffix='.bat', delete=False, prefix='naw_update_')
    bat.write(
        f"@echo off\r\n"
        f"echo Updater started, waiting for exit...\r\n"
        f"timeout /t 3 /nobreak >nul\r\n"
        f":wait\r\n"
        f'tasklist /fi "imagename eq {name}" 2>nul | find /i "{name}" >nul\r\n'
        f"if not errorlevel 1 (\r\n"
        f"    timeout /t 1 /nobreak >nul\r\n"
        f"    goto wait\r\n"
        f")\r\n"
        f"echo Step 1: creating backup\r\n"
        f'if exist "{bak}" del /f /q "{bak}"\r\n'
        f'move /y "{exe}" "{bak}"\r\n'
        f"echo Step 2: placing new version\r\n"
        f'move /y "{newExeTmp}" "{exe}"\r\n'
        f"echo Step 3: clearing cache\r\n"
        f'if exist "{runtime_cache}" rmdir /s /q "{runtime_cache}"\r\n'
        f"echo Step 4: restarting\r\n"
        f'start "" "{exe}"\r\n'
        f"echo Done!\r\n"
        f"timeout /t 3 /nobreak >nul\r\n"
        f'del "%~f0"\r\n'
    )
    bat.close()

    CREATE_NEW_CONSOLE = 0x00000010
    subprocess.Popen(['cmd', '/c', bat.name],
                     creationflags=CREATE_NEW_CONSOLE,
                     close_fds=True)


def _isFrozen():
    """Detecteer zowel PyInstaller (sys.frozen) als Nuitka (__compiled__)."""
    if getattr(sys, 'frozen', False):
        return True
    try:
        __compiled__  # noqa: F821  — Nuitka zet dit in gecompileerde modules
        return True
    except NameError:
        return False


def runUpdateFlow(currentVersion):
    """
    True  → update wordt geïnstalleerd, caller moet afsluiten.
    False → geen update (of afgewezen), caller gaat gewoon door.
    """
    if not _isFrozen():
        return False
    if sys.platform != 'win32':
        return False

    result = _checkRemote(currentVersion)
    if not result:
        return False
    latest, url = result
    if not url:
        return False
    if not _askUser(latest, currentVersion):
        return False

    try:
        # Download naar de AppData-map die al is uitgesloten bij Defender
        _dl_dir = os.path.join(os.environ.get('LOCALAPPDATA', tempfile.gettempdir()),
                               'NerdsAdWar', 'updates')
        os.makedirs(_dl_dir, exist_ok=True)
        tmp = os.path.join(_dl_dir, f'NerdsAdWar-{latest}.exe')
        _download(url, tmp)
    except Exception as e:
        _showError(f"Download mislukt:\n{e}")
        return False

    try:
        _replaceAndRestart(tmp)
    except Exception as e:
        _showError(f"Kon update niet starten:\n{e}")
        return False

    return True
