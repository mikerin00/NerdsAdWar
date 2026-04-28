# Module: accounts
# Account management — server-authoritative with local cache for offline play.
#
# register / login  →  relay server (register always needs internet;
#                       login falls back to local cache when offline)
# getActiveUser     →  local cache only  (fast, no network, called every frame)
# updateStats       →  local cache + background server sync
# setAvatar         →  local only  (it's a device file path)

import hashlib
import json
import os
import socket
import threading
import time
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


# ── Relay helpers ─────────────────────────────────────────────────────────────

def _relayCall(msg_type: str, data: dict, timeout: float = 8.0):
    """Send one request to the relay account endpoint. Returns (t, d)."""
    from src.net.protocol import sendMessage, recvMessage
    from src.net.internet import VPS_HOST, VPS_PORT
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((VPS_HOST, VPS_PORT))
        sendMessage(sock, msg_type, data)
        return recvMessage(sock)
    finally:
        try:
            sock.close()
        except Exception:
            pass


def _saveLocalCache(server_acc: dict, pw_hash: str) -> None:
    """Merge a server account record into the local cache.
    Stores pw_hash locally for offline login + background stat sync.
    Keeps the existing local avatar (device-specific file path)."""
    _ensureDir()
    local  = _loadAccounts()
    key    = server_acc['username'].strip().lower()
    avatar = local.get(key, {}).get('avatar')
    merged = dict(server_acc)
    merged['password'] = pw_hash
    merged['avatar']   = avatar
    local[key] = merged
    _saveAccounts(local)


def _loginLocal(key: str, password: str):
    """Offline fallback: validate against local cache."""
    accounts = _loadAccounts()
    if key not in accounts:
        return False, 'Account niet gevonden (geen verbinding met server).'
    acc = accounts[key]
    if acc.get('password') != _hash(password):
        return False, 'Onjuist wachtwoord.'
    _saveSession(acc['username'])
    return True, acc


# ── Public API ────────────────────────────────────────────────────────────────

def register(username: str, password: str):
    """Returns (True, account_dict) or (False, error_str).
    Always requires a server connection."""
    name = username.strip()
    if len(name) < 2:
        return False, 'Naam moet minimaal 2 tekens zijn.'
    if len(name) > 24:
        return False, 'Naam mag maximaal 24 tekens zijn.'
    if not all(c.isalnum() or c in ' _-.' for c in name):
        return False, 'Naam mag alleen letters, cijfers, spaties, _ - . bevatten.'
    if len(password) < 4:
        return False, 'Wachtwoord moet minimaal 4 tekens zijn.'
    try:
        pw_hash = _hash(password)
        t, d = _relayCall('acc_register', {'username': name, 'password': pw_hash})
        if t == 'acc_err':
            return False, d.get('reason', 'Registratie mislukt.')
        if t == 'acc_ok':
            account = d['account']
            _saveLocalCache(account, pw_hash)
            _saveSession(account['username'])
            startHeartbeat()
            return True, account
        return False, 'Onverwacht serverantwoord.'
    except Exception:
        return False, 'Geen verbinding met de server. Controleer je internet.'


def login(username: str, password: str):
    """Returns (True, account_dict) or (False, error_str).
    Tries server first; falls back to local cache when offline."""
    key = username.strip().lower()
    if not key:
        return False, 'Vul een gebruikersnaam in.'

    pw_hash = _hash(password)

    try:
        t, d = _relayCall('acc_login', {'username': key, 'password': pw_hash})
        if t == 'acc_err':
            reason = d.get('reason', 'Inloggen mislukt.')
            # Account bestaat nog niet op server — auto-migreer vanuit local cache
            if 'niet gevonden' in reason:
                local_acc = _loadAccounts().get(key)
                if local_acc and local_acc.get('password') == pw_hash:
                    _migrateToServer(local_acc)
                    _saveSession(local_acc['username'])
                    return True, local_acc
            return False, reason
        if t == 'acc_ok':
            account = d['account']
            _saveLocalCache(account, pw_hash)
            _saveSession(account['username'])
            startHeartbeat()
            return True, account
        return False, 'Onverwacht serverantwoord.'
    except Exception:
        # Server niet bereikbaar — val terug op local cache
        ok, acc = _loginLocal(key, password)
        if ok:
            startHeartbeat()
        return ok, acc


def _migrateToServer(local_acc: dict) -> None:
    """Push een bestaand local-only account naar de server (best-effort, background)."""
    def _work():
        try:
            _relayCall('acc_register', {
                'username': local_acc['username'],
                'password': local_acc.get('password', ''),
            }, timeout=10.0)
        except Exception:
            pass
    threading.Thread(target=_work, daemon=True).start()


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
    """Update stats locally, then sync to server in the background."""
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

    pw_hash = accounts[key].get('password', '')
    threading.Thread(
        target=_syncStats,
        args=(key, pw_hash, dict(stats)),
        daemon=True,
    ).start()


def _syncStats(username_key: str, pw_hash: str, stats: dict) -> None:
    try:
        _relayCall('acc_sync', {
            'username': username_key,
            'password': pw_hash,
            'stats':    stats,
        }, timeout=10.0)
    except Exception:
        pass  # offline — local al bijgewerkt, synct volgende keer


# ── Online presence ───────────────────────────────────────────────────────────

_heartbeat_running = False
_heartbeat_lock    = threading.Lock()


def startHeartbeat() -> None:
    """Start een achtergrond-thread die elke 30 seconden een heartbeat stuurt.
    Stopt automatisch als de gebruiker uitlogt. Veilig om meerdere keren te
    roepen — start alleen één thread tegelijk."""
    global _heartbeat_running
    with _heartbeat_lock:
        if _heartbeat_running:
            return
        _heartbeat_running = True

    def _work():
        global _heartbeat_running
        while True:
            user = getActiveUser()
            if not user:
                with _heartbeat_lock:
                    _heartbeat_running = False
                return
            try:
                _relayCall('acc_heartbeat', {
                    'username': user['username'].lower(),
                    'password': user.get('password', ''),
                }, timeout=5.0)
            except Exception:
                pass
            time.sleep(30)

    threading.Thread(target=_work, daemon=True).start()


# ── Friends ───────────────────────────────────────────────────────────────────

def getFriends() -> list:
    """Haal vriendenlijst op van de server. Elk item: {username, online, stats}.
    Geeft [] bij fout of geen verbinding."""
    user = getActiveUser()
    if not user:
        return []
    try:
        t, d = _relayCall('acc_friends_get', {
            'username': user['username'].lower(),
            'password': user.get('password', ''),
        })
        return d.get('friends', []) if t == 'acc_ok' else []
    except Exception:
        return []


def addFriend(friend_username: str):
    """Returns (True, '') of (False, error_str)."""
    user = getActiveUser()
    if not user:
        return False, 'Niet ingelogd.'
    try:
        t, d = _relayCall('acc_friend_add', {
            'username': user['username'].lower(),
            'password': user.get('password', ''),
            'friend':   friend_username.strip().lower(),
        })
        if t == 'acc_err':
            return False, d.get('reason', 'Mislukt.')
        return True, ''
    except Exception:
        return False, 'Geen verbinding met de server.'


def removeFriend(friend_username: str) -> None:
    """Verwijder vriend (best-effort, geen foutmelding)."""
    user = getActiveUser()
    if not user:
        return
    try:
        _relayCall('acc_friend_remove', {
            'username': user['username'].lower(),
            'password': user.get('password', ''),
            'friend':   friend_username.strip().lower(),
        }, timeout=5.0)
    except Exception:
        pass


def setAvatar(username: str, path: str) -> None:
    """Avatar wordt alleen lokaal opgeslagen (het is een apparaat-bestandspad)."""
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
