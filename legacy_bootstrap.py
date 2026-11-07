"""Bootstrap older POSIX Hermes versions through their same-user control protocol."""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import socket
import stat
import struct
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


def private_node(path, kind, *, home=False):
    node = path.lstat()
    check = {"directory": stat.S_ISDIR, "socket": stat.S_ISSOCK}[kind]
    forbidden = 0o022 if home else 0o077
    if not check(node.st_mode) or node.st_uid != os.getuid() or node.st_mode & forbidden:
        raise ValueError("Unsafe gateway control path")


def control_path(home):
    private_node(home, "directory", home=True)
    direct = home / "gateway.sock"
    if os.path.lexists(direct):
        private_node(direct, "socket")
        return direct
    pointer = home / "gateway.sock.path"
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(pointer, flags), "rb") as stream:
        node = os.fstat(stream.fileno())
        if not stat.S_ISREG(node.st_mode) or node.st_uid != os.getuid() or node.st_mode & 0o077:
            raise ValueError("Unsafe gateway control pointer")
        data = stream.read(4097)
    if len(data) > 4096:
        raise ValueError("Invalid gateway control pointer")
    path = Path(data.decode("utf-8").strip())
    digest = hashlib.sha256(os.path.normcase(str(home.resolve())).encode()).hexdigest()[:16]
    if not path.is_absolute() or path.name != "control.sock" or path.parent.name != f"hermes-gw-{digest}":
        raise ValueError("Invalid gateway control pointer")
    private_node(path.parent, "directory")
    private_node(path, "socket")
    return path


def verify_peer(peer):
    if hasattr(socket, "SO_PEERCRED"):
        uid = struct.unpack("3i", peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
    else:
        # macOS/BSD expose getpeereid through libc rather than Python's socket API.
        libc = ctypes.CDLL(None, use_errno=True)
        uid_value, gid_value = ctypes.c_uint(), ctypes.c_uint()
        if libc.getpeereid(peer.fileno(), ctypes.byref(uid_value), ctypes.byref(gid_value)) != 0:
            raise OSError("Could not authenticate gateway control peer")
        uid = uid_value.value
    if uid != os.getuid():
        raise ValueError("Gateway control peer belongs to another user")


def session_ticket(home, endpoint):
    request = {"protocol": 1, "id": 1, "verb": "session-ticket", "params": {
        "profile_id": endpoint["profile_id"], "instance_id": endpoint["instance_id"],
        "purpose": "interactive",
    }}
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
        peer.settimeout(5)
        peer.connect(str(control_path(home)))
        verify_peer(peer)
        peer.sendall(json.dumps(request).encode() + b"\n")
        data = bytearray()
        while b"\n" not in data:
            chunk = peer.recv(4096)
            if not chunk or len(data) + len(chunk) > 65536:
                raise ValueError("Invalid gateway control response")
            data.extend(chunk)
    response = json.loads(data.split(b"\n", 1)[0])
    if response.get("ok") is not True or response.get("protocol") != 1 or response.get("id") != 1:
        raise ValueError("Gateway refused the session ticket")
    grant = response.get("result", {})
    if any(grant.get(key) != endpoint[key] for key in ("profile_id", "instance_id", "runtime_protocol")):
        raise ValueError("Gateway identity changed during bootstrap; retry launch")
    ticket = grant.get("ticket")
    if not isinstance(ticket, str) or not ticket:
        raise ValueError("Gateway returned no session ticket")
    return ticket


def attach_legacy(executable):
    if os.name != "posix":
        raise ValueError("This Hermes version needs gateway attach support on Windows; update Hermes")
    result = subprocess.run([executable, "gateway", "ensure", "--json"],
                            capture_output=True, text=True, timeout=90, check=False)
    if result.returncode:
        raise ValueError("Gateway ensure failed; run `hermes gateway status` for details")
    receipt = json.loads(result.stdout)
    endpoint = receipt.get("endpoint") or {}
    if receipt.get("state") != "ready" or endpoint.get("runtime_protocol") != 1:
        raise ValueError("Gateway is not ready or uses an unsupported runtime protocol")
    origin = urlsplit(endpoint["api_origin"])
    if origin.scheme != "http" or origin.hostname not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("Legacy bootstrap requires a loopback gateway")
    home = Path(endpoint.get("control_home") or endpoint["profile_id"])
    ticket = session_ticket(home, endpoint)
    protocol = "hermes-gateway-v1"
    return {"url": "ws://" + origin.netloc + "/api/ws", "protocol": protocol,
            "protocols": [protocol, "hermes-gateway-ticket." + ticket]}
