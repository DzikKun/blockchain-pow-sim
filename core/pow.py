"""Proof of Work untuk simulasi blockchain (kontrak AGENT.md 6.2).

Mining berjalan di proses pemanggil (tanpa thread/process tambahan) supaya
tidak terkena GIL dan sesuai batasan ``1 node = 1 proses``.
"""

from __future__ import annotations

from typing import Callable, Optional

from .block import Block

#: Difficulty maksimum yang diizinkan proyek (AGENT.md bagian 3).
MAX_DIFFICULTY = 5

#: ``should_stop`` tidak dicek tiap iterasi agar loop tetap cepat.
STOP_CHECK_INTERVAL = 1000


def _target_prefix(difficulty: int) -> str:
    """Validasi difficulty dan kembalikan prefix target (mis. ``'000'``)."""
    assert isinstance(difficulty, int), "difficulty harus int"
    assert (
        0 <= difficulty <= MAX_DIFFICULTY
    ), f"difficulty harus 0..{MAX_DIFFICULTY}, dapat {difficulty}"
    return "0" * difficulty


def mine(
    block: Block,
    difficulty: int,
    should_stop: Optional[Callable[[], bool]] = None,
) -> tuple[Optional[Block], int]:
    """Cari nonce sehingga ``block.hash`` diawali ``difficulty`` karakter '0'.

    Args:
        block: blok yang akan ditambang. ``nonce`` dan ``hash`` dimutasi di
            tempat (baik saat berhasil maupun saat dihentikan).
        difficulty: jumlah karakter '0' di awal hash (0..5).
        should_stop: callable tanpa argumen. Dicek **tiap 1000 percobaan**;
            jika mengembalikan ``True`` mining berhenti lebih awal.

    Returns:
        ``(block, attempts)`` jika berhasil, atau ``(None, attempts)`` bila
        dihentikan. ``attempts`` = jumlah hash yang benar-benar dihitung.
    """
    target = _target_prefix(difficulty)
    attempts = 0

    while True:
        attempts += 1
        block.hash = block.compute_hash()
        if block.hash.startswith(target):
            return block, attempts

        block.nonce += 1

        # Cek callback secara berkala, bukan tiap iterasi (biaya + responsivitas).
        if (
            should_stop is not None
            and attempts % STOP_CHECK_INTERVAL == 0
            and should_stop()
        ):
            return None, attempts


def is_valid_pow(block: Block, difficulty: int) -> bool:
    """True jika ``block`` punya hash konsisten dan memenuhi target difficulty."""
    target = _target_prefix(difficulty)
    if len(block.hash) != 64:
        return False
    if block.compute_hash() != block.hash:
        return False
    return block.hash.startswith(target)
