# Module: net.protocol
# Wire format: each message is a 4-byte big-endian length prefix followed by
# UTF-8 JSON payload. Both Host and Client use these helpers so framing stays
# in sync. JSON keeps debugging trivial; we can swap to msgpack later if the
# state-snapshot bandwidth becomes a problem.

import json
import socket
import struct

PROTOCOL_VERSION = 1
DEFAULT_PORT     = 50777

# Message types (kept short — they're sent every snapshot)
MSG_HELLO    = 'hi'    # initial greeting from each side: protocol version + role
MSG_LOBBY    = 'lob'   # lobby state: ready flags, seed, biome, etc.
MSG_READY    = 'rdy'   # toggle ready in lobby
MSG_PICK     = 'pick'  # client picks a color index (lobby only)
MSG_START    = 'go'    # host signals: game is starting
MSG_SNAPSHOT = 'snap'  # (Phase 2) host → client: world state
MSG_COMMAND  = 'cmd'   # (Phase 3) client → host: player input
MSG_BYE      = 'bye'   # graceful disconnect


class ProtocolError(Exception):
    """Raised when the wire format is violated or a peer disconnects."""


def sendMessage(sock: socket.socket, msgType: str, data: dict) -> None:
    """Frame and send a single JSON message. Blocks until fully sent."""
    payload = json.dumps({'t': msgType, 'd': data}, separators=(',', ':')).encode('utf-8')
    header  = struct.pack('>I', len(payload))
    sock.sendall(header + payload)


def recvExact(sock: socket.socket, n: int) -> bytes:
    """Read exactly n bytes or raise ProtocolError on EOF."""
    chunks = []
    remaining = n
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ProtocolError("peer closed connection")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b''.join(chunks)


def recvMessage(sock: socket.socket):
    """Read one framed message. Returns (msgType, data) or raises ProtocolError."""
    header = recvExact(sock, 4)
    (length,) = struct.unpack('>I', header)
    if length == 0 or length > 8 * 1024 * 1024:
        raise ProtocolError(f"invalid message length: {length}")
    body = recvExact(sock, length)
    try:
        msg = json.loads(body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ProtocolError(f"malformed JSON: {e}")
    if not isinstance(msg, dict) or 't' not in msg or 'd' not in msg:
        raise ProtocolError("malformed message envelope")
    return msg['t'], msg['d']


def getLocalIp() -> str:
    """Best-effort: find the LAN IP this machine uses for outbound traffic.
    Doesn't actually send anything — UDP socket connect is just a routing query."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))   # arbitrary unreachable address
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()
