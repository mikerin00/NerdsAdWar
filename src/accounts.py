# Module: accounts
# Local account management — register, login, session, stats, progress paths.

import hashlib
import json
import os
from datetime import datetime

_DATA_DIR      = os.path.join(os.getcwd(), 'accounts')
_ACCOUNTS_FILE = os.path.join(_DATA_DIR, 'accounts.json')
_SESSION_FILE  = os.path.join(_DATA_DIR, 'session.json')


def _ensureDir():
    os.makedirs(_DATA_DIR, exist_ok=True)


def _loadAccounts() -> dict:
    try:
        with open(_ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _saveAccounts(data: dict) -> None:
    _ensureDir()
    try:
        with open(_ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _defaultStats() -> dict:
    return {
        'campaign_wins':   0,
        'campaign_losses': 0,
        'fog_wins':        0,
        'record_wave':     0,
        'total_wins':      0,
        'total_losses':    0,
        'games_played':    0,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def register(username: str, password: str):
    """Returns (True, account_dict) or (False, error_str)."""
    name = username.strip()
    if len(name) < 2:
        return False, "Naam moet minimaal 2 tekens zijn."
    if len(name) > 24:
        return False, "Naam mag maximaal 24 tekens zijn."
    if not all(c.isalnum() or c in ' _-.' for c in name):
        return False, "Naam mag alleen letters, cijfers, spaties, _ - . bevatten."
    if len(password) < 4:
        return False, "Wachtwoord moet minimaal 4 tekens zijn."
    accounts = _loadAccounts()
    key = name.lower()
    if key in accounts:
        return False, "Deze gebruikersnaam is al in gebruik."
    account = {
        'username': name,
        'password': _hash(password),
        'created':  datetime.now().strftime('%d-%m-%Y'),
        'avatar':   None,
        'stats':    _defaultStats(),
    }
    accounts[key] = account
    _saveAccounts(accounts)
    _saveSession(name)
    return True, account


def login(username: str, password: str):
    """Returns (True, account_dict) or (False, error_str)."""
    accounts = _loadAccounts()
    key = username.strip().lower()
    if not key:
        return False, "Vul een gebruikersnaam in."
    if key not in accounts:
        return False, "Account niet gevonden."
    acc = accounts[key]
    if acc['password'] != _hash(password):
        return False, "Onjuist wachtwoord."
    _saveSession(acc['username'])
    return True, acc


def logout() -> None:
    try:
        os.remove(_SESSION_FILE)
    except OSError:
        pass


def _saveSession(username: str) -> None:
    _ensureDir()
    try:
        with open(_SESSION_FILE, 'w', encoding='utf-8') as f:
            json.dump({'username': username}, f)
    except OSError:
        pass


def getActiveUser() -> dict | None:
    """Returns the current account dict, or None if not logged in."""
    try:
        with open(_SESSION_FILE, 'r', encoding='utf-8') as f:
            d = json.load(f)
        key = d.get('username', '').strip().lower()
        if not key:
            return None
        return _loadAccounts().get(key)
    except Exception:
        return None


def updateStats(username: str, **kwargs) -> None:
    """Increment/update stats. record_wave takes max; all others increment."""
    accounts = _loadAccounts()
    key = username.strip().lower()
    if key not in accounts:
        return
    stats = accounts[key].setdefault('stats', _defaultStats())
    for k, v in kwargs.items():
        if k == 'record_wave':
            stats['record_wave'] = max(int(stats.get('record_wave', 0)), int(v))
        else:
            stats[k] = int(stats.get(k, 0)) + int(v)
    _saveAccounts(accounts)


def setAvatar(username: str, path: str) -> None:
    accounts = _loadAccounts()
    key = username.strip().lower()
    if key not in accounts:
        return
    accounts[key]['avatar'] = path
    _saveAccounts(accounts)


# ── Per-user progress file paths ──────────────────────────────────────────────

def campaignProgressFile() -> str:
    """Path to the active user's campaign_progress.json (fallback: global)."""
    user = getActiveUser()
    if user is None:
        return os.path.join(os.getcwd(), 'campaign_progress.json')
    d = os.path.join(_DATA_DIR, user['username'].lower())
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, 'campaign_progress.json')


def tutorialProgressFile() -> str:
    """Path to the active user's tutorial_progress.json (fallback: global)."""
    user = getActiveUser()
    if user is None:
        return os.path.join(os.getcwd(), 'tutorial_progress.json')
    d = os.path.join(_DATA_DIR, user['username'].lower())
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, 'tutorial_progress.json')
