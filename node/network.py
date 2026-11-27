"""Transport TCP localhost dengan pesan JSON berbatas newline."""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Callable
from typing import Any


MessageHandler = Callable[[dict[str, Any]], None]
MAX_MESSAGE_BYTES = 16 * 1024 * 1024


def send(port: int, message_dict: dict[str, Any], timeout: float = 1.5) -> bool:
    """Kirim satu pesan JSON ke localhost; koneksi gagal tidak menghentikan node."""
    try:
        payload = json.dumps(message_dict, separators=(",", ":")).encode("utf-8") + b"\n"
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as conn:
            conn.settimeout(timeout)
            conn.sendall(payload)
        return True
    except (OSError, TypeError, ValueError):
        return False


def broadcast(
    peers: list[int], message_dict: dict[str, Any], timeout: float = 1.5
) -> None:
    """Kirim pesan ke peer secara paralel agar peer offline tidak menumpuk timeout."""
    senders = [
        threading.Thread(
            target=send,
            args=(port, message_dict, timeout),
            name=f"node-send-{port}",
            daemon=True,
        )
        for port in peers
    ]
    for sender in senders:
        sender.start()
    for sender in senders:
        sender.join(timeout=timeout + 0.1)


class Network:
    """Server TCP yang menyerahkan pesan JSON valid ke handler."""

    def __init__(
        self,
        port: int,
        handler: MessageHandler,
        host: str = "127.0.0.1",
    ) -> None:
        self.port = port
        self.handler = handler
        self.host = host
        self._socket: socket.socket | None = None
        self._accept_thread: threading.Thread | None = None
        self._stopping = threading.Event()

    def start(self) -> None:
        """Bind port dan mulai menerima koneksi."""
        if self._socket is not None:
            return

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen()
        server.settimeout(0.2)
        self._socket = server
        self._stopping.clear()
        self._accept_thread = threading.Thread(
            target=self._accept_connections,
            name=f"node-network-{self.port}",
            daemon=True,
        )
        self._accept_thread.start()

    def stop(self) -> None:
        """Hentikan listener dan tunggu thread accept selesai."""
        self._stopping.set()
        server, self._socket = self._socket, None
        if server is not None:
            server.close()
        thread, self._accept_thread = self._accept_thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def send(self, port: int, message_dict: dict[str, Any]) -> bool:
        return send(port, message_dict)

    def broadcast(self, peers: list[int], message_dict: dict[str, Any]) -> None:
        broadcast(peers, message_dict)

    def _accept_connections(self) -> None:
        server = self._socket
        if server is None:
            return
        while not self._stopping.is_set():
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            except OSError:
                if self._stopping.is_set():
                    return
                raise
            threading.Thread(
                target=self._handle_connection,
                args=(conn,),
                name=f"node-connection-{self.port}",
                daemon=True,
            ).start()

    def _handle_connection(self, conn: socket.socket) -> None:
        with conn:
            chunks = bytearray()
            while len(chunks) <= MAX_MESSAGE_BYTES:
                try:
                    chunk = conn.recv(min(65536, MAX_MESSAGE_BYTES + 1 - len(chunks)))
                except OSError:
                    return
                if not chunk:
                    return
                newline = chunk.find(b"\n")
                if newline >= 0:
                    chunks.extend(chunk[:newline])
                    try:
                        message = json.loads(chunks.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        return
                    if isinstance(message, dict):
                        self.handler(message)
                    return
                chunks.extend(chunk)
            return
