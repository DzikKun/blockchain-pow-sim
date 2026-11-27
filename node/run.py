"""CLI entry point: ``python -m node.run``."""

from __future__ import annotations

import argparse

from .node import Node


def _ports(value: str) -> list[int]:
    if not value.strip():
        return []
    try:
        ports = [int(part.strip()) for part in value.split(",") if part.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("peers harus berupa daftar port") from exc
    if any(not 1 <= port <= 65535 for port in ports):
        raise argparse.ArgumentTypeError("port peer harus berada pada rentang 1..65535")
    return ports


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Jalankan satu node PoW")
    parser.add_argument("--id", type=int, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--peers", type=_ports, default=[])
    parser.add_argument("--difficulty", type=int, required=True)
    parser.add_argument("--blocks", type=int, required=True)
    parser.add_argument("--log", required=True)
    args = parser.parse_args(argv)
    if args.id < 0:
        parser.error("--id tidak boleh negatif")
    if not 1 <= args.port <= 65535:
        parser.error("--port harus berada pada rentang 1..65535")
    if not 0 <= args.difficulty <= 5:
        parser.error("--difficulty harus berada pada rentang 0..5")
    if args.blocks < 1:
        parser.error("--blocks minimal 1")
    if args.port in args.peers:
        parser.error("--port node tidak boleh tercantum di --peers")
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    node = Node(
        id=args.id,
        port=args.port,
        peers=args.peers,
        difficulty=args.difficulty,
        blocks_target=args.blocks,
        log_path=args.log,
    )
    node.run()


if __name__ == "__main__":
    main()
