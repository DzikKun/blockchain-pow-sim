"""Tes jaringan node dan integrasi dua node pada localhost."""

from __future__ import annotations

import json
import socket
import threading
import time

import pytest

from core import Block, Blockchain, mine
from node.network import Network, send
from node.node import Node


def free_node_ports(count: int) -> list[int]:
    sockets: list[socket.socket] = []
    try:
        for port in range(5000, 5016):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                sock.close()
                continue
            sockets.append(sock)
            if len(sockets) == count:
                return [sock.getsockname()[1] for sock in sockets]
        pytest.skip("Tidak tersedia cukup port lokal 5000..5015 untuk uji node")
    finally:
        for sock in sockets:
            sock.close()


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for(predicate, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_network_sends_and_receives_json_messages():
    port = free_port()
    received: list[dict] = []
    arrived = threading.Event()

    def handler(message):
        received.append(message)
        arrived.set()

    network = Network(port, handler)
    network.start()
    try:
        assert send(port, {"type": "TX", "tx": {"amount": 4}})
        assert arrived.wait(2.0)
        assert received == [{"type": "TX", "tx": {"amount": 4}}]
    finally:
        network.stop()


def test_network_handles_unavailable_peer_without_raising():
    assert send(free_port(), {"type": "GET_CHAIN", "sender": 0}) is False


def test_two_nodes_reach_identical_chain(tmp_path):
    ports = free_node_ports(2)
    nodes = [
        Node(ports[0] - 5000, ports[0], [ports[1]], difficulty=1, blocks_target=3,
             log_path=tmp_path / "node0.jsonl"),
        Node(ports[1] - 5000, ports[1], [ports[0]], difficulty=1, blocks_target=3,
             log_path=tmp_path / "node1.jsonl"),
    ]
    errors: list[BaseException] = []

    def run_node(node):
        try:
            node.run()
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run_node, args=(node,)) for node in nodes]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10.0)

    for node in nodes:
        node.stop()
    assert not errors
    assert all(not thread.is_alive() for thread in threads)
    assert nodes[0].chain.to_list() == nodes[1].chain.to_list()
    assert len(nodes[0].chain.chain) >= 4


def test_node_syncs_chain_from_peer(tmp_path):
    peer_port, node_port = free_node_ports(2)

    peer = Node(peer_port - 5000, peer_port, [], difficulty=1, blocks_target=3,
                log_path=tmp_path / "peer.jsonl")
    with peer._chain_lock:
        block = peer.chain.new_block([])
        mined, _ = mine(block, peer.difficulty)
        assert mined is not None
        assert peer.chain.add_block(mined)
    peer.start()

    node = Node(node_port - 5000, node_port, [peer_port], difficulty=1, blocks_target=3,
                log_path=tmp_path / "node.jsonl")
    node.start()
    try:
        node._request_chain(peer_port)
        assert wait_for(lambda: len(node.chain.chain) == 2)
        assert node.chain.to_list() == peer.chain.to_list()
    finally:
        node.stop()
        peer.stop()


def test_node_rejects_tampered_block(tmp_path):
    port = free_port()
    node = Node(port - 5000, port, [], difficulty=1, blocks_target=1,
                log_path=tmp_path / "node.jsonl")
    block = Block(
        index=1,
        timestamp=1.0,
        transactions=[],
        prev_hash=node.chain.last_block.hash,
    )
    mined, _ = mine(block, 1)
    assert mined is not None
    mined.hash = "f" * 64

    node._receive_block(
        {
            "type": "NEW_BLOCK",
            "block": mined.to_dict(),
            "sender": 1,
            "sent_at": time.time(),
        }
    )

    assert len(node.chain.chain) == 1
    if (tmp_path / "node.jsonl").exists():
        events = [
            json.loads(line)
            for line in (tmp_path / "node.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        assert all(event["event"] != "block_received" for event in events)
