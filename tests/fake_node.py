"""Node palsu untuk menguji ``bench/run_experiments.py`` tanpa ``node/``.

Menerima argumen CLI yang sama dengan node asli (kontrak 6.5), menulis event
JSONL sintetis, lalu keluar. Node 0 menghasilkan ``block_mined`` dan satu
``fork_detected``; node lain menghasilkan ``block_received`` dengan latensi
tetap 10 ms.

Variabel lingkungan:
- ``FAKE_NODE_SLEEP``: detik tidur sebelum menulis (untuk uji timeout).
- ``FAKE_NODE_FAIL``: ``1`` membuat proses keluar dengan kode 1.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Node palsu untuk test bench.")
    parser.add_argument("--id", type=int, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--peers", default="")
    parser.add_argument("--difficulty", type=int, default=1)
    parser.add_argument("--blocks", type=int, required=True)
    parser.add_argument("--log", required=True)
    args, _unknown = parser.parse_known_args(argv)
    return args


def build_events(node_id: int, blocks: int) -> list[dict]:
    now = time.time()
    events: list[dict] = []

    if node_id == 0:
        for index in range(1, blocks + 1):
            events.append(
                {
                    "t": now + index * 0.001,
                    "node": node_id,
                    "event": "block_mined",
                    "index": index,
                    "hash": "0" * 64,
                    "attempts": 16,
                }
            )
        if blocks >= 2:
            events.append(
                {
                    "t": now + 0.002,
                    "node": node_id,
                    "event": "fork_detected",
                    "index": 2,
                }
            )
    else:
        for index in range(1, blocks + 1):
            received = now + index * 0.001
            events.append(
                {
                    "t": received,
                    "node": node_id,
                    "event": "block_received",
                    "index": index,
                    "sender": 0,
                    "sent_at": received - 0.010,
                }
            )

    return events


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    delay = float(os.environ.get("FAKE_NODE_SLEEP", "0") or 0)
    if delay > 0:
        time.sleep(delay)

    if os.environ.get("FAKE_NODE_FAIL") == "1":
        return 1

    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as handle:
        for event in build_events(args.id, args.blocks):
            handle.write(json.dumps(event) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
