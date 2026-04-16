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
# Upload bij elke release BEIDE bestanden: NerdsAdWar2.exe + Setup_NerdsAdWar2_vX.Y.exe
# De updater downloadt automatisch de NerdsAdWar2.exe uit de nieuwste release.
UPDATE_REPO = "mikerin00/NerdsAdWar"
# ────────────────────────────────────────────────────────────────────────────

_TIMEOUT_CHECK    = 3.0    # seconden voor de API-check
_TIMEOUT_DOWNLOAD = 120.0  # seconden voor de download
_UA = {'User-Agent': 'NerdsAdWar-Updater'}


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
    msg = (f"Er is een nieuwe versie van Nerds ad War 2 beschikbaar!\n\n"
           f"   Huidig:  {current}\n"
           f"   Nieuw:   {latest}\n\n"
           f"Nu downloaden en installeren?")
    MB_YESNO = 0x04
    MB_INFO  = 0x40
    IDYES    = 6
    return ctypes.windll.user32.MessageBoxW(
        None, msg, "Update beschikbaar", MB_YESNO | MB_INFO) == IDYES


def _showError(text):
    ctypes.windll.user32.MessageBoxW(None, text, "Update fout", 0x10)


def _download(url, dest):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=_TIMEOUT_DOWNLOAD) as r, \
         open(dest, 'wb') as f:
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            f.write(chunk)


def _replaceAndRestart(newExeTmp):
    """
    Swap de draaiende exe voor newExeTmp via een losse batch-file.
    Windows laat een draaiende exe niet overschrijven, maar wel hernoemen —
    dus we hernoemen huidige naar .old, zetten nieuwe op zijn plek, herstarten.
    """
    exe  = sys.executable
    bak  = exe + '.old'
    name = os.path.basename(exe)

    bat = tempfile.NamedTemporaryFile(
        mode='w', suffix='.bat', delete=False, prefix='naw_update_')
    bat.write(
        f"@echo off\r\n"
        f":wait\r\n"
        f"timeout /t 1 /nobreak >nul\r\n"
        f'tasklist /fi "imagename eq {name}" | find /i "{name}" >nul && goto wait\r\n'
        f'if exist "{bak}" del /f /q "{bak}"\r\n'
        f'move /y "{exe}" "{bak}"\r\n'
        f'move /y "{newExeTmp}" "{exe}"\r\n'
        f'start "" "{exe}"\r\n'
        f'del "%~f0"\r\n'
    )
    bat.close()

    DETACHED_PROCESS = 0x00000008
    subprocess.Popen(['cmd', '/c', bat.name],
                     creationflags=DETACHED_PROCESS,
                     close_fds=True)


def runUpdateFlow(currentVersion):
    """
    True  → update wordt geïnstalleerd, caller moet afsluiten.
    False → geen update (of afgewezen), caller gaat gewoon door.
    """
    if not getattr(sys, 'frozen', False):
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
        tmp = os.path.join(tempfile.gettempdir(),
                           f'NerdsAdWar2-{latest}.exe')
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
