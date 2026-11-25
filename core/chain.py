"""Rantai blok, genesis deterministik, dan resolusi longest chain (kontrak 6.3)."""

from __future__ import annotations

import time
from typing import Any

from .block import Block
from .pow import MAX_DIFFICULTY, is_valid_pow

#: Nilai tetap genesis agar semua node menghasilkan genesis yang identik.
GENESIS_PREV_HASH = "0" * 64
GENESIS_TIMESTAMP = 0.0
GENESIS_NONCE = 0


def create_genesis_block() -> Block:
    """Buat genesis yang deterministik di semua node.

    Genesis sengaja **tidak** ditambang (tidak wajib memenuhi PoW) supaya
    hash-nya sama untuk difficulty berapa pun. Validasi genesis dilakukan
    dengan membandingkan seluruh isinya terhadap template ini.
    """
    genesis = Block(
        index=0,
        timestamp=GENESIS_TIMESTAMP,
        transactions=[],
        prev_hash=GENESIS_PREV_HASH,
        nonce=GENESIS_NONCE,
    )
    genesis.hash = genesis.compute_hash()
    return genesis


class Blockchain:
    """Rantai blok dengan aturan validasi dan penggantian longest chain."""

    def __init__(self, difficulty: int):
        assert (
            0 <= difficulty <= MAX_DIFFICULTY
        ), f"difficulty harus 0..{MAX_DIFFICULTY}, dapat {difficulty}"
        self.difficulty = difficulty
        self.chain: list[Block] = [create_genesis_block()]

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    def new_block(self, transactions: list[dict]) -> Block:
        """Blok baru yang belum ditambang, tersambung ke blok terakhir."""
        return Block(
            index=self.last_block.index + 1,
            timestamp=time.time(),
            transactions=list(transactions),
            prev_hash=self.last_block.hash,
            nonce=0,
        )

    def add_block(self, block: Block) -> bool:
        """Tambahkan blok jika index, prev_hash, hash, dan PoW-nya valid."""
        if not isinstance(block, Block):
            return False
        if block.index != self.last_block.index + 1:
            return False
        if block.prev_hash != self.last_block.hash:
            return False
        if block.compute_hash() != block.hash:
            return False
        if not is_valid_pow(block, self.difficulty):
            return False

        self.chain.append(block)
        return True

    def is_valid_chain(self, chain: list[Block]) -> bool:
        """Validasi penuh: genesis benar, tautan benar, hash benar, PoW valid."""
        if not chain:
            return False

        # Genesis harus persis sama dengan template deterministik.
        if chain[0].to_dict() != create_genesis_block().to_dict():
            return False

        for i in range(1, len(chain)):
            current = chain[i]
            previous = chain[i - 1]

            if current.index != previous.index + 1:
                return False
            if current.prev_hash != previous.hash:
                return False
            if current.compute_hash() != current.hash:
                return False
            if not is_valid_pow(current, self.difficulty):
                return False

        return True

    def replace_chain(self, new_chain: list[Block]) -> bool:
        """Ganti chain hanya jika lebih panjang **dan** valid (longest chain)."""
        if len(new_chain) <= len(self.chain):
            return False
        if not self.is_valid_chain(new_chain):
            return False

        self.chain = list(new_chain)
        return True

    def to_list(self) -> list[dict[str, Any]]:
        """Serialisasi seluruh chain menjadi list of dict."""
        return [block.to_dict() for block in self.chain]
