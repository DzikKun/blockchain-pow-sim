"""Struktur blok dan hashing SHA-256 (kontrak AGENT.md 6.1).

Aturan hashing:
- Hash dihitung dari ``index, timestamp, transactions, prev_hash, nonce``
  (field ``hash`` sendiri tidak ikut di-hash).
- Serialisasi JSON memakai ``sort_keys=True`` dan separator rapat agar
  hasilnya deterministik di semua proses/node.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

# Urutan field sesuai kontrak. Dipakai juga oleh test.
HASH_FIELDS: tuple[str, ...] = (
    "index",
    "timestamp",
    "transactions",
    "prev_hash",
    "nonce",
)


@dataclass
class Block:
    """Satu blok pada rantai.

    Atribut publik mengikuti kontrak 6.1. ``hash`` diisi oleh :func:`core.pow.mine`
    atau :meth:`compute_hash`; blok baru boleh memiliki ``hash`` kosong.
    """

    index: int
    timestamp: float
    transactions: list[dict]
    prev_hash: str
    nonce: int = 0
    hash: str = ""

    def _payload(self) -> dict[str, Any]:
        """Representasi field yang ikut di-hash (tanpa ``hash``)."""
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "prev_hash": self.prev_hash,
            "nonce": self.nonce,
        }

    def compute_hash(self) -> str:
        """SHA-256 heksadesimal dari isi blok, deterministik.

        ``timestamp`` bertipe float sehingga JSON memakai representasi
        round-trip Python yang stabil; ``transactions`` wajib berisi tipe
        JSON murni (dict/list/str/int/float/bool/None).
        """
        raw = json.dumps(
            self._payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialisasi lengkap (termasuk ``hash``) untuk jaringan/JSONL."""
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "prev_hash": self.prev_hash,
            "nonce": self.nonce,
            "hash": self.hash,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Block":
        """Kebalikan :meth:`to_dict`; tahan terhadap field opsional yang hilang."""
        return Block(
            index=int(d["index"]),
            timestamp=float(d["timestamp"]),
            transactions=list(d.get("transactions") or []),
            prev_hash=str(d["prev_hash"]),
            nonce=int(d.get("nonce", 0)),
            hash=str(d.get("hash", "")),
        )
