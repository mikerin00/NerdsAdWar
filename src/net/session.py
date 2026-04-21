# Module: net.session
# Host and Client wrappers around a TCP socket. Both run a background thread
# that pushes incoming messages onto a thread-safe queue; the main game loop
# polls that queue with no blocking, so rendering stays smooth.
#
# Phase 1 scope: connect, exchange hello + lobby state + ready toggle, signal
# game start. Snapshots/commands come in later phases.

import queue
import socket
import threading

from src.net.protocol import (
    PROTOCOL_VERSION, DEFAULT_PORT,
    MSG_HELLO, MSG_BYE, MSG_LOBBY,
    sendMessage, recvMessage, ProtocolError,
)


class _Session:
    """Common base: owns one connected socket + RX thread + send lock."""

    def __init__(self, sock: socket.socket, role: str):
        self._sock     = sock
        self._sendLock = threading.Lock()
        self._inbox    = queue.Queue()
        self._alive    = True
        self.role      = role          # 'host' or 'client'
        self.peerName  = None          # filled after HELLO
        self._rxThread = threading.Thread(target=self._rxLoop, daemon=True)
        self._rxThread.start()

    def _rxLoop(self):
        try:
            while self._alive:
                msg = recvMessage(self._sock)
                self._inbox.put(msg)
        except (ProtocolError, OSError) as e:
            self._inbox.put(('__error__', {'reason': str(e)}))
        finally:
            self._alive = False

    def send(self, msgType: str, data: dict):
        if not self._alive:
            return False
        try:
            with self._sendLock:
                sendMessage(self._sock, msgType, data)
            return True
        except OSError as e:
            self._inbox.put(('__error__', {'reason': str(e)}))
            self._alive = False
            return False

    def poll(self):
        """Yield all pending (msgType, data) pairs without blocking."""
        out = []
        while True:
            try:
                out.append(self._inbox.get_nowait())
            except queue.Empty:
                break
        return out

    @property
    def alive(self) -> bool:
        return self._alive

    def close(self):
        if not self._alive:
            return
        self._alive = False
        try:
            with self._sendLock:
                sendMessage(self._sock, MSG_BYE, {})
        except Exception:
            pass
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            self._sock.close()
        except Exception:
            pass


# ── Host: accept up to N clients, hand each an assigned slot ────────────────

class HostServer:
    """Listens for incoming clients and assigns each a slot index (1..N).
    Used for both 1v1 (max 1 client → slot 1) and 2v2 (max 3 → slots 1..3).
    The host itself is always slot 0.

    Thread-safe to query via `newSessions()` each frame — it returns any
    sessions that were accepted since the previous poll.
    """

    def __init__(self, port: int = DEFAULT_PORT, name: str = 'Host',
                 maxClients: int = 1):
        self.port       = port
        self.name       = name
        self.maxClients = maxClients
        # Current dynamic limit (≤ maxClients). Lobby shrinks/grows this when
        # the host switches game-mode so 1v1 won't park a joiner in slot 2.
        self.allowedClients = maxClients
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(('0.0.0.0', port))
        self._sock.listen(max(1, maxClients))
        self._sock.settimeout(0.25)
        self._cancel   = False
        self._error    = None
        self._lock     = threading.Lock()
        self._pending  = []              # sessions accepted but not yet polled
        self._assigned = {}              # slot → session (stable record)
        self._thread   = threading.Thread(target=self._acceptLoop, daemon=True)
        self._thread.start()

    def _nextFreeSlot(self):
        for s in range(1, self.allowedClients + 1):
            if s not in self._assigned or not self._assigned[s].alive:
                return s
        return None

    def setAllowedClients(self, n: int):
        """Lobby calls this on mode-change so 1v1 only hands out slot 1
        and 2v2 hands out 1..3. Clamped to [0, maxClients]."""
        with self._lock:
            self.allowedClients = max(0, min(int(n), self.maxClients))

    def _acceptLoop(self):
        while not self._cancel:
            try:
                conn, addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError as e:
                self._error = str(e)
                return
            conn.settimeout(None)
            try:
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except OSError:
                pass
            with self._lock:
                slot = self._nextFreeSlot()
                if slot is None:
                    # Lobby full — close politely
                    try:
                        conn.close()
                    except Exception:
                        pass
                    continue
                sess = _Session(conn, role='host')
                sess.peerName = f"{addr[0]}:{addr[1]}"
                sess.slot     = slot
                sess.send(MSG_HELLO, {'version': PROTOCOL_VERSION,
                                      'role': 'host', 'name': self.name,
                                      'slot': slot})
                self._assigned[slot] = sess
                self._pending.append(sess)

    def newSessions(self):
        """Return any sessions accepted since last call, clearing the queue."""
        with self._lock:
            out = list(self._pending)
            self._pending.clear()
        return out

    def allSessions(self):
        """Return currently-alive sessions keyed by slot."""
        with self._lock:
            return {s: se for s, se in self._assigned.items() if se.alive}

    @property
    def error(self):
        return self._error

    def close(self):
        self._cancel = True
        try:
            self._sock.close()
        except Exception:
            pass


# Backwards-compat alias — older code referred to HostListener.
HostListener = HostServer


# ── Client: connect to host, return a _Session ─────────────────────────────

class ClientConnector:
    """Async connect attempt to a host. Use poll() to check status.
    Status: 'connecting' | 'connected' | 'failed'."""

    def __init__(self, host: str, port: int = DEFAULT_PORT, name: str = 'Player 2'):
        self.host    = host
        self.port    = port
        self.name    = name
        self.status  = 'connecting'
        self.error   = None
        self.session = None
        self._thread = threading.Thread(target=self._connect, daemon=True)
        self._thread.start()

    def _connect(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((self.host, self.port))
            sock.settimeout(None)
            try:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except OSError:
                pass
        except (OSError, socket.timeout) as e:
            self.error  = str(e)
            self.status = 'failed'
            return
        sess = _Session(sock, role='client')
        sess.peerName = f"{self.host}:{self.port}"
        sess.send(MSG_HELLO, {'version': PROTOCOL_VERSION,
                              'role': 'client', 'name': self.name})
        self.session = sess
        self.status  = 'connected'

    def cancel(self):
        # If still connecting we can't easily abort the blocking connect, but
        # the 5s timeout will resolve on its own. If already connected, close.
        if self.session:
            self.session.close()


# ── Lobby state helper ──────────────────────────────────────────────────────

class LobbyState:
    """Synchronised lobby state — host is authoritative on seed/biome/mode,
    both sides report their own ready flag, host broadcasts the merged view."""

    def __init__(self, role: str):
        self.role        = role
        self.peerVersion = None
        self.peerHello   = False
        self.selfReady   = False
        self.peerReady   = False
        self.seed        = None    # set by host
        self.biome       = None
        self.difficulty  = None    # ignored in MP for now (no AI)
        self.gamemode    = 'STANDAARD'
