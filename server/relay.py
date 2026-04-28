#!/usr/bin/env python3
"""
Nerds at War — VPS Relay Server
Run on Hetzner CAX11:  python3 relay.py [--port 50777]

Protocol (all messages use 4-byte big-endian length + UTF-8 JSON):

  rl_host       client→relay  Register as a host      {name, mode, slots}
  rl_ok         relay→host    Confirmed                {id}
  rl_ping       relay→host    Heartbeat                {}
  rl_pong       host→relay    Heartbeat reply          {}
  rl_new        relay→host    New client incoming      {slot}
  rl_data       host→relay    Open data channel        {id}
  rl_join       client→relay  Join a host              {id}
  rl_list       client→relay  Request lobby list       {}
  rl_err        relay→any     Error                    {reason}

  acc_register  client→relay  Create account           {username, password}
  acc_login     client→relay  Login                    {username, password}
  acc_sync      client→relay  Push stats to server     {username, password, stats}
  acc_ok        relay→client  Success                  {account?}
  acc_err       relay→client  Failure                  {reason}

After rl_data ↔ rl_join are matched the relay becomes a dumb byte pipe —
the game's own protocol (HELLO, LOBBY, SNAPSHOT …) flows through unchanged.
"""

import json
import os
import random
import socket
import string
import struct
import sys
import threading
import time
from datetime import datetime

PORT      = 50777
HEARTBEAT = 20      # seconds between pings
MAX_IDLE  = 60      # drop host if no pong for this many seconds

# ── Wire framing (mirrors src/net/protocol.py) ───────────────────────────────

def _send(sock, t, d):
    payload = json.dumps({'t': t, 'd': d}, separators=(',', ':')).encode()
    sock.sendall(struct.pack('>I', len(payload)) + payload)

def _recv(sock, timeout=None):
    if timeout is not None:
        sock.settimeout(timeout)
    raw = b''
    while len(raw) < 4:
        chunk = sock.recv(4 - len(raw))
        if not chunk:
            raise ConnectionError("peer closed")
        raw += chunk
    (length,) = struct.unpack('>I', raw)
    if length == 0 or length > 4 * 1024 * 1024:
        raise ConnectionError(f"bad length {length}")
    body = b''
    while len(body) < length:
        chunk = sock.recv(length - len(body))
        if not chunk:
            raise ConnectionError("peer closed")
        body += chunk
    msg = json.loads(body.decode())
    return msg['t'], msg['d']

# ── Lobby registry ────────────────────────────────────────────────────────────

_lock  = threading.Lock()
_hosts = {}
# id -> {name, mode, slots, players, ctrl, ctrl_lock, pending, last_pong}

def _new_id():
    chars = string.ascii_uppercase + string.digits
    with _lock:
        while True:
            h = ''.join(random.choices(chars, k=6))
            if h not in _hosts:
                return h

def _remove_host(host_id):
    with _lock:
        entry = _hosts.pop(host_id, None)
    if entry:
        try:
            entry['ctrl'].close()
        except Exception:
            pass
        print(f"[relay] host {host_id} ({entry['name']}) removed", flush=True)

# ── Byte pipe ─────────────────────────────────────────────────────────────────

def _pipe_loop(src, dst, done):
    try:
        while not done.is_set():
            data = src.recv(4096)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        done.set()

def _start_pipe(sock_a, sock_b):
    done = threading.Event()
    for a, b in ((sock_a, sock_b), (sock_b, sock_a)):
        threading.Thread(target=_pipe_loop, args=(a, b, done), daemon=True).start()

    def _close_when_done():
        done.wait()
        for s in (sock_a, sock_b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                s.close()
            except Exception:
                pass

    threading.Thread(target=_close_when_done, daemon=True).start()

# ── Connection handler ────────────────────────────────────────────────────────

def _handle_host(conn, d):
    host_id = _new_id()
    name    = str(d.get('name', 'Host'))[:16]
    mode    = str(d.get('mode', '1v1'))
    slots   = max(1, min(int(d.get('slots', 2)), 8))

    entry = {
        'name':      name,
        'mode':      mode,
        'slots':     slots,
        'players':   1,
        'ctrl':      conn,
        'ctrl_lock': threading.Lock(),
        'pending':   [],
        'last_pong': time.monotonic(),
    }
    with _lock:
        _hosts[host_id] = entry

    try:
        _send(conn, 'rl_ok', {'id': host_id})
    except Exception:
        _remove_host(host_id)
        return

    print(f"[relay] host {host_id} registered: {name!r} {mode} {slots}p", flush=True)

    # Heartbeat sender
    def _ping_loop():
        while True:
            time.sleep(HEARTBEAT)
            with _lock:
                if host_id not in _hosts:
                    return
                idle = time.monotonic() - entry['last_pong']
            if idle > MAX_IDLE:
                print(f"[relay] host {host_id} timed out", flush=True)
                _remove_host(host_id)
                return
            try:
                with entry['ctrl_lock']:
                    _send(conn, 'rl_ping', {})
            except Exception:
                _remove_host(host_id)
                return

    threading.Thread(target=_ping_loop, daemon=True).start()

    # Control read loop — only pong expected inbound
    try:
        conn.settimeout(MAX_IDLE + 5)
        while True:
            t2, d2 = _recv(conn)
            if t2 == 'rl_pong':
                entry['last_pong'] = time.monotonic()
    except Exception:
        pass

    _remove_host(host_id)


def _handle_data(conn, d):
    host_id = d.get('id', '')
    with _lock:
        entry = _hosts.get(host_id)
        client_conn = entry['pending'].pop(0) if entry and entry['pending'] else None
        if client_conn:
            entry['players'] += 1

    if client_conn is None:
        conn.close()
        return

    _start_pipe(conn, client_conn)


def _handle_join(conn, d):
    host_id = d.get('id', '')
    with _lock:
        entry = _hosts.get(host_id)
        if not entry:
            try:
                _send(conn, 'rl_err', {'reason': 'lobby not found'})
            except Exception:
                pass
            conn.close()
            return
        slot = entry['players']
        entry['pending'].append(conn)
        lock = entry['ctrl_lock']
        ctrl = entry['ctrl']

    try:
        with lock:
            _send(ctrl, 'rl_new', {'slot': slot})
    except Exception:
        with _lock:
            if host_id in _hosts:
                try:
                    _hosts[host_id]['pending'].remove(conn)
                except ValueError:
                    pass
        conn.close()
    # conn stays open — piped when host opens rl_data


def _handle_list(conn):
    with _lock:
        lobbies = [
            {
                'id':      hid,
                'name':    e['name'],
                'mode':    e['mode'],
                'slots':   e['slots'],
                'players': e['players'],
            }
            for hid, e in _hosts.items()
        ]
    try:
        _send(conn, 'rl_list', {'lobbies': lobbies})
    except Exception:
        pass
    conn.close()


# ── Account storage ───────────────────────────────────────────────────────────

_ACC_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'accounts.json')
_acc_lock = threading.Lock()

def _acc_load():
    try:
        with open(_ACC_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _acc_save(data):
    with open(_ACC_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def _acc_default_stats():
    return {'campaign_wins': 0, 'campaign_losses': 0, 'fog_wins': 0,
            'record_wave': 0, 'total_wins': 0, 'total_losses': 0, 'games_played': 0}

def _handle_acc_register(conn, d):
    username = str(d.get('username', '')).strip()
    pw_hash  = str(d.get('password', ''))
    key      = username.lower()

    if not (2 <= len(username) <= 24):
        _send(conn, 'acc_err', {'reason': 'Naam moet 2–24 tekens zijn.'}); conn.close(); return
    if not all(c.isalnum() or c in ' _-.' for c in username):
        _send(conn, 'acc_err', {'reason': 'Ongeldige tekens in naam.'}); conn.close(); return
    if len(pw_hash) != 64:
        _send(conn, 'acc_err', {'reason': 'Ongeldig wachtwoord.'}); conn.close(); return

    with _acc_lock:
        accs = _acc_load()
        if key in accs:
            _send(conn, 'acc_err', {'reason': 'Gebruikersnaam al in gebruik.'}); conn.close(); return
        acc = {'username': username, 'password': pw_hash,
               'created': datetime.now().strftime('%d-%m-%Y'),
               'stats': _acc_default_stats()}
        accs[key] = acc
        _acc_save(accs)

    pub = {k: v for k, v in acc.items() if k != 'password'}
    _send(conn, 'acc_ok', {'account': pub})
    conn.close()
    print(f'[acc] registered {username!r}', flush=True)

def _handle_acc_login(conn, d):
    key     = str(d.get('username', '')).strip().lower()
    pw_hash = str(d.get('password', ''))

    with _acc_lock:
        accs = _acc_load()
        acc  = accs.get(key)

    if not acc:
        _send(conn, 'acc_err', {'reason': 'Account niet gevonden.'}); conn.close(); return
    if acc.get('password') != pw_hash:
        _send(conn, 'acc_err', {'reason': 'Onjuist wachtwoord.'}); conn.close(); return

    pub = {k: v for k, v in acc.items() if k != 'password'}
    _send(conn, 'acc_ok', {'account': pub})
    conn.close()

def _handle_acc_sync(conn, d):
    key     = str(d.get('username', '')).strip().lower()
    pw_hash = str(d.get('password', ''))
    stats   = d.get('stats', {})

    with _acc_lock:
        accs = _acc_load()
        acc  = accs.get(key)
        if not acc or acc.get('password') != pw_hash:
            _send(conn, 'acc_err', {'reason': 'Authenticatie mislukt.'}); conn.close(); return
        srv = acc.setdefault('stats', _acc_default_stats())
        for k, v in stats.items():
            if k in srv:
                srv[k] = max(int(srv.get(k, 0)), int(v))
        _acc_save(accs)

    _send(conn, 'acc_ok', {})
    conn.close()


# ── Connection handler ────────────────────────────────────────────────────────

def _handle(conn, addr):
    try:
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except Exception:
        pass

    try:
        t, d = _recv(conn, timeout=10.0)
    except Exception:
        conn.close()
        return

    conn.settimeout(None)

    if   t == 'rl_host':      _handle_host(conn, d)
    elif t == 'rl_data':      _handle_data(conn, d)
    elif t == 'rl_join':      _handle_join(conn, d)
    elif t == 'rl_list':      _handle_list(conn)
    elif t == 'acc_register': _handle_acc_register(conn, d)
    elif t == 'acc_login':    _handle_acc_login(conn, d)
    elif t == 'acc_sync':     _handle_acc_sync(conn, d)
    else:
        conn.close()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    port = PORT
    if '--port' in sys.argv:
        port = int(sys.argv[sys.argv.index('--port') + 1])

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('0.0.0.0', port))
    srv.listen(64)
    print(f"[relay] Nerds at War relay server — port {port}", flush=True)

    while True:
        conn, addr = srv.accept()
        threading.Thread(target=_handle, args=(conn, addr), daemon=True).start()


if __name__ == '__main__':
    main()
