"""Paket core simulasi blockchain Proof of Work.

Isi:
- :class:`core.block.Block` -- struktur satu blok.
- :func:`core.pow.mine` / :func:`core.pow.is_valid_pow` -- Proof of Work.
- :class:`core.chain.Blockchain` -- rantai blok + validasi + longest chain.
"""

from .block import Block
from .chain import Blockchain, create_genesis_block
from .pow import MAX_DIFFICULTY, is_valid_pow, mine

__all__ = [
    "Block",
    "Blockchain",
    "MAX_DIFFICULTY",
    "create_genesis_block",
    "is_valid_pow",
    "mine",
]
