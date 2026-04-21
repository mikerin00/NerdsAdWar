# Module: net.internet
# Internet multiplayer via VPS relay.
# Drop-in replacements for HostServer and ClientConnector that route through
# the relay instead of connecting peer-to-peer.

import socket
import threading

from src.net.protocol import (
    PROTOCOL_VERSION, DEFAULT_PORT,
    MSG_HELLO, sendMessage, recvMessage, ProtocolError,
)
from src.net.session import _Session

# ── VPS address — set this to your Hetzner IP ────────────────────────────────
VPS_HOST = '178.104.251.209'
VPS_PORT = DEFAULT_PORT   # relay listens on the same port as the game


# ── Low-level relay helpers ───────────────────────────────────────────────────

def _relay_connect(timeout=8.0) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((VPS_HOST, VPS_PORT))
    sock.settimeout(None)
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass
    return sock


# ── Lobby list ────────────────────────────────────────────────────────────────

def fetchLobbies(timeout: float = 4.0) -> list:
    """Return list of open internet lobbies from the relay.
    Each entry: {name, mode, slots, players, id, via_relay=True}
    Returns [] on any error."""
    try:
        sock = _relay_connect(timeout=timeout)
        sendMessage(sock, 'rl_list', {})
        t, d = recvMessage(sock)
        sock.close()
        if t != 'rl_list':
            return []
        result = []
        for entry in d.get('lobbies', []):
            result.append({
                'name':      entry.get('name', '?'),
                'mode':      entry.get('mode', '1v1'),
                'slots':     int(entry.get('slots', 2)),
                'players':   int(entry.get('players', 1)),
                'id':        entry.get('id', ''),
                'via_relay': True,
            })
        return result
    except Exception:
        return []


# ── InternetHost — mirrors HostServer interface ───────────────────────────────

class InternetHost:
    """Registers on the relay as a host.  Mirrors HostServer.newSessions() /
    allSessions() / close() / error so _HostLobby can poll both together."""

    def __init__(self, name: str, maxClients: int = 7):
        self.name       = name
        self.maxClients = maxClients
        self._id        = None
        self._ctrl      = None
        self._ctrl_lock = threading.Lock()
        self._lock      = threading.Lock()
        self._pending   = []          # _Session objects not yet polled
        self._assigned  = {}          # slot → _Session
        self._next_slot = 1
        self._cancel    = False
        self.error      = None
        self.allowedClients = maxClients

        self._thread = threading.Thread(target=self._register, daemon=True)
        self._thread.start()

    def _next_free_slot(self):
        for s in range(1, self.allowedClients + 1):
            if s not in self._assigned or not self._assigned[s].alive:
                return s
        return None

    def _register(self):
        try:
            sock = _relay_connect()
            sendMessage(sock, 'rl_host', {
                'name':  self.name,
                'mode':  '1v1',
                'slots': self.maxClients + 1,
            })
            t, d = recvMessage(sock)
            if t != 'rl_ok':
                raise ProtocolError(f"unexpected relay response: {t}")
            self._id   = d['id']
            self._ctrl = sock
        except Exception as e:
            self.error = str(e)
            return

        self._ctrl_loop()

    def _ctrl_loop(self):
        """Read rl_new / rl_ping from control connection; open data channel
        for each rl_new."""
        try:
            while not self._cancel:
                t, d = recvMessage(self._ctrl)
                if t == 'rl_ping':
                    with self._ctrl_lock:
                        sendMessage(self._ctrl, 'rl_pong', {})
                elif t == 'rl_new':
                    self._open_data_channel()
        except Exception:
            pass

    def _open_data_channel(self):
        if not self._id:
            return
        try:
            sock = _relay_connect()
            sendMessage(sock, 'rl_data', {'id': self._id})
            # Relay now pipes this socket to the waiting client.
            # Assign a slot and send MSG_HELLO exactly as HostServer does.
            with self._lock:
                slot = self._next_free_slot()
                if slot is None:
                    sock.close()
                    return
            sess = _Session(sock, role='host')
            sess.slot     = slot
            sess.peerName = f'relay/{self._id}'
            sess.send(MSG_HELLO, {
                'version': PROTOCOL_VERSION,
                'role':    'host',
                'name':    self.name,
                'slot':    slot,
            })
            with self._lock:
                self._assigned[slot] = sess
                self._pending.append(sess)
        except Exception:
            pass

    # ── HostServer-compatible interface ──────────────────────────────────────

    def setAllowedClients(self, n: int):
        with self._lock:
            self.allowedClients = max(0, min(int(n), self.maxClients))

    def newSessions(self):
        with self._lock:
            out = list(self._pending)
            self._pending.clear()
        return out

    def allSessions(self):
        with self._lock:
            return {s: se for s, se in self._assigned.items() if se.alive}

    @property
    def relay_id(self) -> str:
        return self._id or ''

    def close(self):
        self._cancel = True
        if self._ctrl:
            try:
                self._ctrl.close()
            except Exception:
                pass


# ── InternetClient — mirrors ClientConnector interface ────────────────────────

class InternetClient:
    """Joins a relay lobby by host ID.  Mirrors ClientConnector."""

    def __init__(self, host_id: str, name: str):
        self.host_id = host_id
        self.name    = name
        self.status  = 'connecting'
        self.error   = None
        self.session = None
        self._thread = threading.Thread(target=self._connect, daemon=True)
        self._thread.start()

    def _connect(self):
        try:
            sock = _relay_connect(timeout=10.0)
            sendMessage(sock, 'rl_join', {'id': self.host_id})
            # Relay tells host → host opens data channel → relay starts piping.
            # From this point sock is a transparent tunnel to the host.
            sess = _Session(sock, role='client')
            sess.peerName = f'relay/{self.host_id}'
            sess.send(MSG_HELLO, {
                'version': PROTOCOL_VERSION,
                'role':    'client',
                'name':    self.name,
            })
            self.session = sess
            self.status  = 'connected'
        except Exception as e:
            self.error  = str(e)
            self.status = 'failed'

    def cancel(self):
        if self.session:
            self.session.close()
