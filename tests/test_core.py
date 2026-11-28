"""Test untuk kontrak core blockchain (AGENT.md 6.1-6.3)."""

from __future__ import annotations

import copy
import time

import pytest

from core.block import Block
from core.chain import Blockchain, create_genesis_block
from core.pow import MAX_DIFFICULTY, is_valid_pow, mine


def make_block(index: int = 1, prev_hash: str = "a" * 64) -> Block:
    return Block(
        index=index,
        timestamp=1700000000.0,
        transactions=[{"from": "alice", "to": "bob", "amount": 5}],
        prev_hash=prev_hash,
    )


def mine_block(block: Block, difficulty: int = 2) -> Block:
    mined, attempts = mine(block, difficulty)
    assert mined is not None
    assert attempts >= 1
    return mined


def build_chain(difficulty: int, n_blocks: int) -> Blockchain:
    """Bangun chain dengan ``n_blocks`` blok (di luar genesis)."""
    chain = Blockchain(difficulty)
    for i in range(n_blocks):
        block = chain.new_block([{"n": i}])
        assert chain.add_block(mine_block(block, difficulty))
    return chain


def build_tagged_chain(difficulty: int, timestamps: list[float]) -> Blockchain:
    """Bangun chain dengan timestamp tetap agar hash-nya deterministik.

    Dipakai untuk menguji tie-break rantai sama panjang (PC-001).
    """
    chain = Blockchain(difficulty)
    for i, timestamp in enumerate(timestamps):
        block = Block(
            index=i + 1,
            timestamp=timestamp,
            transactions=[{"n": i}],
            prev_hash=chain.last_block.hash,
            nonce=0,
        )
        assert chain.add_block(mine_block(block, difficulty))
    return chain


# ---------------------------------------------------------------- Block


def test_hash_is_deterministic():
    a = make_block()
    b = make_block()

    assert a.compute_hash() == b.compute_hash()
    assert len(a.compute_hash()) == 64
    assert a.compute_hash() != make_block(index=2).compute_hash()


def test_hash_changes_when_content_changes():
    block = make_block()
    original = block.compute_hash()

    block.nonce += 1
    assert block.compute_hash() != original

    block = make_block()
    block.transactions[0]["amount"] = 999
    assert block.compute_hash() != original


def test_hash_does_not_include_hash_field():
    block = make_block()
    block.hash = "deadbeef"
    assert block.compute_hash() == make_block().compute_hash()


def test_serialization_roundtrip():
    block = mine_block(make_block(), difficulty=2)
    clone = Block.from_dict(block.to_dict())

    assert clone.to_dict() == block.to_dict()
    assert clone.compute_hash() == block.hash


def test_serialization_survives_json_like_values():
    block = mine_block(make_block(), difficulty=2)
    clone = Block.from_dict(copy.deepcopy(block.to_dict()))

    assert clone.transactions == block.transactions
    assert clone.hash == block.hash


# ------------------------------------------------------------------ PoW


def test_mine_finds_valid_hash():
    block = make_block()
    mined, attempts = mine(block, difficulty=2)

    assert mined is block
    assert attempts >= 1
    assert block.hash.startswith("00")
    assert is_valid_pow(block, 2)
    assert block.compute_hash() == block.hash


def test_mine_difficulty_three_finishes_quickly():
    block = make_block()
    started = time.perf_counter()
    mined, attempts = mine(block, difficulty=3)
    elapsed = time.perf_counter() - started

    assert mined is not None
    assert block.hash.startswith("000")
    assert attempts >= 1
    assert elapsed < 5.0, f"mining difficulty 3 terlalu lambat: {elapsed:.2f}s"


def test_mine_can_be_stopped():
    block = make_block()

    def should_stop() -> bool:
        return True

    mined, attempts = mine(block, difficulty=MAX_DIFFICULTY, should_stop=should_stop)

    assert mined is None
    assert attempts == 1000
    assert attempts % 1000 == 0


def test_mine_ignores_false_should_stop():
    def should_stop() -> bool:
        return False

    block = make_block()
    mined, _ = mine(block, difficulty=2, should_stop=should_stop)

    # should_stop yang selalu False tidak boleh membatalkan mining.
    assert mined is not None
    assert is_valid_pow(block, 2)


def test_mine_rejects_difficulty_above_max():
    with pytest.raises(AssertionError):
        mine(make_block(), MAX_DIFFICULTY + 1)


def test_is_valid_pow_rejects_wrong_difficulty():
    block = mine_block(make_block(), difficulty=3)

    assert is_valid_pow(block, 3)
    assert not is_valid_pow(block, 4)


def test_is_valid_pow_rejects_tampered_hash():
    block = mine_block(make_block(), difficulty=2)
    block.hash = "0" * 64

    assert not is_valid_pow(block, 2)


# ---------------------------------------------------------------- Chain


def test_genesis_is_deterministic_across_difficulties():
    genesis = create_genesis_block()

    assert genesis.index == 0
    assert genesis.prev_hash == "0" * 64
    assert genesis.transactions == []

    for difficulty in (1, 3, 5):
        chain = Blockchain(difficulty)
        assert chain.chain[0].to_dict() == genesis.to_dict()
        assert chain.chain[0].hash == genesis.hash


def test_new_block_links_to_last_block():
    chain = Blockchain(2)
    block = chain.new_block([{"a": 1}])

    assert block.index == 1
    assert block.prev_hash == chain.last_block.hash
    assert block.transactions == [{"a": 1}]
    assert block.hash == ""


def test_add_valid_block():
    chain = Blockchain(2)
    block = mine_block(chain.new_block([{"a": 1}]), difficulty=2)

    assert chain.add_block(block) is True
    assert len(chain.chain) == 2
    assert chain.last_block is block


def test_add_block_rejects_wrong_index():
    chain = Blockchain(2)
    block = mine_block(chain.new_block([]), difficulty=2)
    block.index = 5

    assert chain.add_block(block) is False
    assert len(chain.chain) == 1


def test_add_block_rejects_wrong_prev_hash():
    chain = Blockchain(2)
    block = mine_block(chain.new_block([]), difficulty=2)
    block.prev_hash = "b" * 64

    assert chain.add_block(block) is False


def test_add_block_rejects_invalid_pow():
    chain = Blockchain(2)
    block = chain.new_block([])
    block.compute_hash()  # hash sah tapi tidak memenuhi target difficulty

    assert chain.add_block(block) is False


def test_add_block_rejects_non_block():
    chain = Blockchain(2)
    assert chain.add_block({"index": 1}) is False


def test_is_valid_chain_accepts_good_chain():
    chain = build_chain(difficulty=2, n_blocks=3)
    assert chain.is_valid_chain(chain.chain)


def test_is_valid_chain_rejects_tampered_transaction():
    chain = build_chain(difficulty=2, n_blocks=3)
    chain.chain[1].transactions[0]["n"] = "diubah"

    assert not chain.is_valid_chain(chain.chain)


def test_is_valid_chain_rejects_tampered_genesis():
    chain = build_chain(difficulty=2, n_blocks=2)
    chain.chain[0].timestamp = 123.0

    assert not chain.is_valid_chain(chain.chain)


def test_is_valid_chain_rejects_broken_link():
    chain = build_chain(difficulty=2, n_blocks=2)
    chain.chain[2].prev_hash = "c" * 64

    assert not chain.is_valid_chain(chain.chain)


def test_is_valid_chain_rejects_empty():
    chain = Blockchain(2)
    assert not chain.is_valid_chain([])


def test_replace_chain_accepts_longer_valid_chain():
    short = build_chain(difficulty=2, n_blocks=1)
    longer = build_chain(difficulty=2, n_blocks=3)

    assert short.replace_chain(longer.chain) is True
    assert len(short.chain) == 4
    assert short.to_list() == longer.to_list()


def test_replace_chain_rejects_shorter_chain():
    longer = build_chain(difficulty=2, n_blocks=3)
    shorter = build_chain(difficulty=2, n_blocks=1)

    assert longer.replace_chain(shorter.chain) is False
    assert len(longer.chain) == 4


def test_replace_chain_accepts_equal_length_with_smaller_last_hash():
    winner = build_tagged_chain(2, [1700000000.0, 1700000100.0])
    loser = build_tagged_chain(2, [1700000100.0, 1700000200.0])

    # Penjaga urutan: hash terakhir `winner` harus lebih kecil dari `loser`.
    assert winner.last_block.hash < loser.last_block.hash

    assert loser.replace_chain(winner.chain) is True
    assert loser.to_list() == winner.to_list()


def test_replace_chain_rejects_equal_length_with_larger_last_hash():
    winner = build_tagged_chain(2, [1700000000.0, 1700000100.0])
    loser = build_tagged_chain(2, [1700000100.0, 1700000200.0])

    assert winner.last_block.hash < loser.last_block.hash

    assert winner.replace_chain(loser.chain) is False
    assert winner.to_list() != loser.to_list()


def test_replace_chain_rejects_invalid_longer_chain():
    chain = build_chain(difficulty=2, n_blocks=1)
    fake = build_chain(difficulty=2, n_blocks=3)
    fake.chain[2].transactions[0]["n"] = "palsu"

    assert chain.replace_chain(fake.chain) is False
    assert len(chain.chain) == 2


def test_to_list_roundtrip():
    chain = build_chain(difficulty=2, n_blocks=3)
    payload = chain.to_list()

    assert len(payload) == 4
    assert all(isinstance(item, dict) for item in payload)
    rebuilt = [Block.from_dict(item) for item in payload]
    assert chain.is_valid_chain(rebuilt)
