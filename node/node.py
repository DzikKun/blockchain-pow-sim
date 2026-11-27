"""Logika mining, sinkronisasi, dan event untuk satu node blockchain."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from core import Block, Blockchain, mine

from .network import Network

PORT_BASE = 5000
SYNC_STARTUP_SECONDS = 1.0
SYNC_RETRY_SECONDS = 0.2
MINER_STAGGER_SECONDS = 0.1


class Node:
    """Satu node blockchain, berjalan sebagai proses tersendiri pada runtime."""

    def __init__(
        self,
        id: int,
        port: int,
        peers: list[int],
        difficulty: int,
        blocks_target: int,
        log_path: str | Path,
    ) -> None:
        if not 0 <= difficulty <= 5:
            raise ValueError("difficulty harus berada pada rentang 0..5")
        if blocks_target < 1:
            raise ValueError("blocks_target minimal 1")
        if any(peer == port for peer in peers):
            raise ValueError("port node tidak boleh tercantum sebagai peer")

        self.id = id
        self.port = port
        self.peers = list(dict.fromkeys(peers))
        self.difficulty = difficulty
        self.blocks_target = blocks_target
        self.log_path = Path(log_path)
        self.chain = Blockchain(difficulty)
        self._chain_lock = threading.RLock()
        self._log_lock = threading.Lock()
        self._stop_mining = threading.Event()
        self._network = Network(port, self._handle_message)

    def start(self) -> None:
        self._network.start()

    def stop(self) -> None:
        self._stop_mining.set()
        self._network.stop()

    def run(self) -> None:
        """Mulai server, sinkronisasi awal, lalu mining hingga target tercapai."""
        self.start()
        try:
            self._synchronize_at_startup()
            time.sleep(self.id * MINER_STAGGER_SECONDS)
            self._mine_until_target()
        finally:
            self.stop()

    def _synchronize_at_startup(self) -> None:
        deadline = time.monotonic() + SYNC_STARTUP_SECONDS
        next_request = 0.0
        while time.monotonic() < deadline:
            now = time.monotonic()
            if now >= next_request:
                self._request_chains()
                next_request = now + SYNC_RETRY_SECONDS
            time.sleep(0.02)

    def _request_chains(self) -> None:
        message = {"type": "GET_CHAIN", "sender": self.id}
        self._network.broadcast(self.peers, message)

    def _mine_until_target(self) -> None:
        while not self._target_reached():
            self._stop_mining.clear()
            with self._chain_lock:
                candidate = self.chain.new_block([])

            mined, attempts = mine(
                candidate,
                self.difficulty,
                should_stop=self._stop_mining.is_set,
            )
            if mined is None:
                continue

            with self._chain_lock:
                accepted = self.chain.add_block(mined)
                index = self.chain.last_block.index

            self._write_event(
                "block_mined",
                index=mined.index,
                hash=mined.hash,
                attempts=attempts,
            )
            if accepted:
                sent_at = time.time()
                self._network.broadcast(
                    self.peers,
                    {
                        "type": "NEW_BLOCK",
                        "block": mined.to_dict(),
                        "sender": self.id,
                        "sent_at": sent_at,
                    },
                )
                self._stop_mining.wait(0.01)
            elif self._target_reached(index):
                return

    def _target_reached(self, index: int | None = None) -> bool:
        if index is None:
            with self._chain_lock:
                index = self.chain.last_block.index
        return index >= self.blocks_target

    def _handle_message(self, message: dict[str, Any]) -> None:
        message_type = message.get("type")
        if message_type == "GET_CHAIN":
            sender = self._sender_port(message)
            if sender is None:
                return
            with self._chain_lock:
                chain_data = self.chain.to_list()
            self._network.send(
                sender,
                {"type": "CHAIN", "chain": chain_data, "sender": self.id},
            )
        elif message_type == "NEW_BLOCK":
            self._receive_block(message)
        elif message_type == "CHAIN":
            self._receive_chain(message)
        elif message_type == "TX":
            return

    def _receive_block(self, message: dict[str, Any]) -> None:
        sender = self._sender_port(message)
        sent_at = message.get("sent_at")
        try:
            block = Block.from_dict(message["block"])
        except (KeyError, TypeError, ValueError):
            if sender is not None:
                self._request_chain(sender)
            return

        with self._chain_lock:
            old_length = len(self.chain.chain)
            accepted = self.chain.add_block(block)
            current_index = self.chain.last_block.index

        if accepted:
            self._stop_mining.set()
            fields: dict[str, Any] = {
                "index": block.index,
                "sender": message.get("sender"),
            }
            if isinstance(sent_at, (int, float)):
                fields["sent_at"] = sent_at
            self._write_event("block_received", **fields)
            return

        if block.index > current_index or (
            block.index == current_index and block.index > 0
        ):
            self._write_event("fork_detected", index=block.index)
        if sender is not None and (block.index >= current_index or old_length == 1):
            self._request_chain(sender)

    def _receive_chain(self, message: dict[str, Any]) -> None:
        try:
            chain_data = message["chain"]
            if not isinstance(chain_data, list):
                return
            new_chain = [Block.from_dict(item) for item in chain_data]
        except (KeyError, TypeError, ValueError):
            return

        with self._chain_lock:
            old_length = len(self.chain.chain)
            replaced = self.chain.replace_chain(new_chain)
            new_length = len(self.chain.chain)

        if replaced:
            self._stop_mining.set()
            self._write_event(
                "chain_replaced",
                old_len=old_length,
                new_len=new_length,
            )

    def _request_chain(self, port: int) -> None:
        self._network.send(
            port,
            {"type": "GET_CHAIN", "sender": self.id},
        )

    @staticmethod
    def _sender_port(message: dict[str, Any]) -> int | None:
        sender = message.get("sender")
        if isinstance(sender, bool) or not isinstance(sender, int) or sender < 0:
            return None
        return PORT_BASE + sender

    def _write_event(self, event: str, **fields: Any) -> None:
        record = {"t": time.time(), "node": self.id, "event": event, **fields}
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, separators=(",", ":"), ensure_ascii=False)
        with self._log_lock:
            with self.log_path.open("a", encoding="utf-8", newline="\n") as log_file:
                log_file.write(line + "\n")
