# Module: accounts
# Account management — volledig lokaal, geen serververbinding nodig.

import hashlib
import json
import os

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
        return False, 'Naam moet minimaal 2 tekens zijn.'
    if len(name) > 24:
        return False, 'Naam mag maximaal 24 tekens zijn.'
    if not all(c.isalnum() or c in ' _-.' for c in name):
        return False, 'Naam mag alleen letters, cijfers, spaties, _ - . bevatten.'
    if len(password) < 4:
        return False, 'Wachtwoord moet minimaal 4 tekens zijn.'

    key      = name.lower()
    pw_hash  = _hash(password)
    accounts = _loadAccounts()

    if key in accounts:
        return False, 'Gebruikersnaam al in gebruik.'

    account = {
        'username': name,
        'password': pw_hash,
        'stats':    _defaultStats(),
    }
    accounts[key] = account
    _saveAccounts(accounts)
    _saveSession(name)
    return True, account


def login(username: str, password: str):
    """Returns (True, account_dict) or (False, error_str)."""
    key = username.strip().lower()
    if not key:
        return False, 'Vul een gebruikersnaam in.'

    accounts = _loadAccounts()
    acc = accounts.get(key)
    if not acc:
        return False, 'Account niet gevonden.'
    if acc.get('password') != _hash(password):
        return False, 'Onjuist wachtwoord.'

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
    """Returns the current account dict from local cache, or None if not logged in."""
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


def startHeartbeat() -> None:
    pass  # geen server, geen heartbeat nodig


def getFriends() -> list:
    return []


def addFriend(friend_username: str):
    return False, 'Vrienden vereist een serververbinding.'


def removeFriend(friend_username: str) -> None:
    pass


def setAvatar(username: str, path: str) -> None:
    accounts = _loadAccounts()
    key = username.strip().lower()
    if key not in accounts:
        return
    accounts[key]['avatar'] = path
    _saveAccounts(accounts)


# ── Per-user progress file paths ──────────────────────────────────────────────

def campaignProgressFile() -> str:
    user = getActiveUser()
    if user is None:
        return os.path.join(os.getcwd(), 'campaign_progress.json')
    d = os.path.join(_DATA_DIR, user['username'].lower())
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, 'campaign_progress.json')


def tutorialProgressFile() -> str:
    user = getActiveUser()
    if user is None:
        return os.path.join(os.getcwd(), 'tutorial_progress.json')
    d = os.path.join(_DATA_DIR, user['username'].lower())
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, 'tutorial_progress.json')
