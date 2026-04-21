# Module: net.discovery
# LAN host discovery via UDP broadcast.
# Host sends a beacon every second; clients scan for 2 seconds and get a list.

import json
import socket
import threading
import time

from src.net.protocol import DEFAULT_PORT, PROTOCOL_VERSION

DISCOVERY_PORT = 50778
_MAGIC         = "NAW_BEACON"


class HostBeacon:
    """Broadcasts a UDP beacon every second so clients can find us."""

    def __init__(self, hostName: str, gamePort: int = DEFAULT_PORT):
        self._payload = json.dumps({
            'magic':   _MAGIC,
            'version': PROTOCOL_VERSION,
            'name':    hostName,
            'port':    gamePort,
        }).encode('utf-8')
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(1.0)
            while not self._stop.is_set():
                try:
                    sock.sendto(self._payload, ('<broadcast>', DISCOVERY_PORT))
                except Exception:
                    pass
                self._stop.wait(1.0)
            sock.close()
        except Exception:
            pass

    def stop(self):
        self._stop.set()


def scan(timeout: float = 2.0) -> list:
    """
    Listen for beacons for `timeout` seconds.
    Returns list of dicts: [{'name': str, 'ip': str, 'port': int}, ...]
    Duplicates (same ip+port) are filtered out.
    """
    found = {}
    deadline = time.monotonic() + timeout
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', DISCOVERY_PORT))
        sock.settimeout(0.2)
        while time.monotonic() < deadline:
            try:
                data, addr = sock.recvfrom(1024)
                msg = json.loads(data.decode('utf-8'))
                if msg.get('magic') != _MAGIC:
                    continue
                if msg.get('version') != PROTOCOL_VERSION:
                    continue
                ip   = addr[0]
                port = int(msg.get('port', DEFAULT_PORT))
                key  = (ip, port)
                if key not in found:
                    found[key] = {
                        'name': str(msg.get('name', 'Onbekend'))[:16],
                        'ip':   ip,
                        'port': port,
                    }
            except (socket.timeout, json.JSONDecodeError, ValueError, KeyError):
                pass
        sock.close()
    except Exception:
        pass
    return list(found.values())
