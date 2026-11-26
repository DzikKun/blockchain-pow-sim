"""Runner benchmark simulasi blockchain PoW (kontrak AGENT.md 6.5-6.6).

Menjalankan N proses node untuk setiap kombinasi (jumlah node, difficulty) dan
setiap ulangan, mengumpulkan event JSONL, lalu menulis satu baris CSV per run.

Pemakaian:
    python -m bench.run_experiments --machine dzikra --nodes 2,4 \
        --difficulty 1,2,3,4 --blocks 10 --runs 3

Untuk menguji runner tanpa ``node/`` asli:
    python -m bench.run_experiments --machine test --nodes 2 --difficulty 1 \
        --blocks 3 --runs 1 --node-module tests.fake_node
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import psutil

PORT_BASE = 5000
MAX_NODES = 8
MAX_DIFFICULTY = 5

CSV_COLUMNS = [
    "machine",
    "run_id",
    "nodes",
    "difficulty",
    "blocks_target",
    "blocks_confirmed",
    "total_time_s",
    "throughput_bps",
    "avg_block_time_s",
    "avg_sync_latency_ms",
    "forks_detected",
    "orphan_blocks",
    "cpu_avg_pct",
    "status",
]


# ------------------------------------------------------------------ utilitas


def int_list(value: str) -> list[int]:
    """Parse ``"2,4,8"`` menjadi ``[2, 4, 8]`` untuk argparse."""
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if not parts:
        raise argparse.ArgumentTypeError("daftar tidak boleh kosong")
    try:
        return [int(part) for part in parts]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"'{value}' bukan daftar bilangan bulat yang valid"
        ) from exc


def validate_args(args: argparse.Namespace) -> None:
    """Validasi batas proyek sebelum menjalankan proses apa pun."""
    for nodes in args.nodes:
        if not 1 <= nodes <= MAX_NODES:
            raise SystemExit(f"Jumlah node {nodes} di luar batas 1..{MAX_NODES}.")
    for difficulty in args.difficulty:
        if not 0 <= difficulty <= MAX_DIFFICULTY:
            raise SystemExit(
                f"Difficulty {difficulty} di luar batas 0..{MAX_DIFFICULTY}."
            )
    if args.blocks < 1:
        raise SystemExit("--blocks minimal 1.")
    if args.runs < 1:
        raise SystemExit("--runs minimal 1.")
    if args.timeout <= 0:
        raise SystemExit("--timeout harus lebih dari 0 detik.")
    if args.pause < 0:
        raise SystemExit("--pause tidak boleh negatif.")

    if importlib.util.find_spec(args.node_module) is None:
        raise SystemExit(
            f"Modul node '{args.node_module}' tidak ditemukan. "
            "Pastikan node/run.py sudah tersedia, atau gunakan "
            "--node-module tests.fake_node untuk uji runner."
        )

    if args.machine == "kibar" and max(args.nodes) > 4:
        print(
            "[peringatan] Laptop Kibar (2C/4T) tidak disarankan menjalankan "
            "lebih dari 4 node."
        )


def read_events(path: Path) -> list[dict[str, Any]]:
    """Baca JSONL, lewati baris kosong/rusak (mis. tulisan terpotong)."""
    if not path.exists():
        return []

    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _as_index(event: dict[str, Any]) -> int:
    try:
        return int(event.get("index", 0))
    except (TypeError, ValueError):
        return 0


def compute_metrics(
    events: list[dict[str, Any]],
    total_time_s: float,
    cpu_avg_pct: float,
) -> dict[str, float | int]:
    """Hitung metrik kontrak 6.6 dari event satu run."""
    blocks_confirmed = 0
    latencies_ms: list[float] = []
    forks = 0
    mined = 0

    for event in events:
        name = event.get("event")
        if name == "block_mined":
            mined += 1
            blocks_confirmed = max(blocks_confirmed, _as_index(event))
        elif name == "block_received":
            blocks_confirmed = max(blocks_confirmed, _as_index(event))
            sent_at = event.get("sent_at")
            received_at = event.get("t")
            if isinstance(sent_at, (int, float)) and isinstance(
                received_at, (int, float)
            ):
                latencies_ms.append(max(0.0, (received_at - sent_at) * 1000.0))
        elif name == "fork_detected":
            forks += 1

    total_time = max(0.0, float(total_time_s))
    throughput = blocks_confirmed / total_time if total_time > 0 else 0.0
    avg_block_time = total_time / blocks_confirmed if blocks_confirmed > 0 else 0.0
    avg_latency = statistics.mean(latencies_ms) if latencies_ms else 0.0
    orphans = max(0, mined - blocks_confirmed)

    return {
        "blocks_confirmed": blocks_confirmed,
        "total_time_s": round(total_time, 6),
        "throughput_bps": round(throughput, 6),
        "avg_block_time_s": round(avg_block_time, 6),
        "avg_sync_latency_ms": round(avg_latency, 6),
        "forks_detected": forks,
        "orphan_blocks": orphans,
        "cpu_avg_pct": round(min(100.0, max(0.0, cpu_avg_pct)), 3),
    }


def build_command(
    node_module: str,
    node_id: int,
    port: int,
    peers: list[int],
    difficulty: int,
    blocks: int,
    log_path: Path,
) -> list[str]:
    """Susun perintah node sesuai kontrak 6.5."""
    return [
        sys.executable,
        "-m",
        node_module,
        "--id",
        str(node_id),
        "--port",
        str(port),
        "--peers",
        ",".join(str(peer) for peer in peers),
        "--difficulty",
        str(difficulty),
        "--blocks",
        str(blocks),
        "--log",
        str(log_path),
    ]


def _terminate(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def run_once(
    *,
    machine: str,
    run_id: int,
    nodes: int,
    difficulty: int,
    blocks: int,
    timeout: float,
    node_module: str,
    out_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    """Jalankan satu kombinasi dan kembalikan satu baris CSV."""
    stamp = time.strftime("%Y%m%d_%H%M%S")
    run_label = f"{machine}_{stamp}_n{nodes}_d{difficulty}_r{run_id}"
    logs_dir = out_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    ports = [PORT_BASE + node_id for node_id in range(nodes)]
    processes: list[subprocess.Popen] = []
    log_paths: list[Path] = []

    cpu_samples: list[float] = []
    stop_sampling = threading.Event()

    def sample_cpu() -> None:
        # Interval tetap agar persentase tidak bergantung pada waktu panggilan
        # pertama psutil (yang bisa bernilai 0 untuk run sangat pendek).
        while not stop_sampling.is_set():
            value = psutil.cpu_percent(interval=0.2)
            if stop_sampling.is_set():
                break
            cpu_samples.append(value)

    started = time.perf_counter()
    sampler = threading.Thread(target=sample_cpu, daemon=True)
    sampler.start()
    status = "ok"

    try:
        for node_id, port in enumerate(ports):
            log_path = (logs_dir / f"{run_label}_node{node_id}.jsonl").resolve()
            stdout_path = (logs_dir / f"{run_label}_node{node_id}.out").resolve()
            peers = [peer for peer in ports if peer != port]
            command = build_command(
                node_module,
                node_id,
                port,
                peers,
                difficulty,
                blocks,
                log_path,
            )

            with stdout_path.open("wb") as stdout_handle:
                processes.append(
                    subprocess.Popen(
                        command,
                        cwd=str(repo_root),
                        stdout=stdout_handle,
                        stderr=subprocess.STDOUT,
                    )
                )
            log_paths.append(log_path)

        deadline = started + timeout

        while True:
            if all(process.poll() is not None for process in processes):
                break
            if time.perf_counter() >= deadline:
                status = "timeout"
                break
            time.sleep(0.2)
    finally:
        total_time = time.perf_counter() - started
        stop_sampling.set()
        sampler.join(timeout=2)
        # Proses yang masih hidup (timeout / Ctrl+C) dihentikan di sini.
        _terminate(processes)

    if status == "ok" and any(
        process.returncode not in (0, None) for process in processes
    ):
        status = "error"

    if not cpu_samples:
        cpu_samples.append(psutil.cpu_percent(interval=0.2))
    cpu_avg = statistics.mean(cpu_samples)

    events: list[dict[str, Any]] = []
    for log_path in log_paths:
        events.extend(read_events(log_path))

    metrics = compute_metrics(events, total_time, cpu_avg)

    return {
        "machine": machine,
        "run_id": run_id,
        "nodes": nodes,
        "difficulty": difficulty,
        "blocks_target": blocks,
        **metrics,
        "status": status,
    }


# ---------------------------------------------------------------------- CLI


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Jalankan benchmark blockchain PoW multi-node."
    )
    parser.add_argument(
        "--machine",
        default="dzikra",
        choices=["kibar", "dzikra"],
        help="Label mesin untuk nama file CSV (default: dzikra).",
    )
    parser.add_argument(
        "--nodes",
        type=int_list,
        default=[2, 4],
        help="Daftar jumlah node dipisah koma (default: 2,4).",
    )
    parser.add_argument(
        "--difficulty",
        type=int_list,
        default=[1, 2, 3, 4],
        help="Daftar difficulty dipisah koma (default: 1,2,3,4).",
    )
    parser.add_argument(
        "--blocks", type=int, default=10, help="Target blok per run (default: 10)."
    )
    parser.add_argument(
        "--runs", type=int, default=3, help="Ulangan per kombinasi (default: 3)."
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="Timeout per run dalam detik (default: 180).",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=2.0,
        help="Jeda antar-run dalam detik (default: 2).",
    )
    parser.add_argument(
        "--out-dir",
        default="results/raw",
        help="Folder CSV keluaran (default: results/raw).",
    )
    parser.add_argument(
        "--node-module",
        default="node.run",
        help="Modul node yang dijalankan (default: node.run).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    validate_args(args)

    repo_root = Path(__file__).resolve().parent.parent
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    csv_path = out_dir / f"{args.machine}_{stamp}.csv"

    total_runs = len(args.nodes) * len(args.difficulty) * args.runs
    print(
        f"Menjalankan {len(args.nodes)} x {len(args.difficulty)} kombinasi "
        f"x {args.runs} ulangan = {total_runs} run."
    )
    print(f"CSV keluaran: {csv_path}")

    run_id = 0
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        for nodes in args.nodes:
            for difficulty in args.difficulty:
                for repetition in range(1, args.runs + 1):
                    run_id += 1
                    print(
                        f"[{run_id}/{total_runs}] node={nodes} "
                        f"difficulty={difficulty} ulangan={repetition} ...",
                        end=" ",
                        flush=True,
                    )
                    row = run_once(
                        machine=args.machine,
                        run_id=run_id,
                        nodes=nodes,
                        difficulty=difficulty,
                        blocks=args.blocks,
                        timeout=args.timeout,
                        node_module=args.node_module,
                        out_dir=out_dir,
                        repo_root=repo_root,
                    )
                    writer.writerow(row)
                    handle.flush()
                    print(
                        f"{row['status']} "
                        f"({row['blocks_confirmed']} blok, "
                        f"{row['total_time_s']:.2f} s, "
                        f"{row['throughput_bps']:.2f} blok/dtk)"
                    )

                    if run_id < total_runs and args.pause > 0:
                        time.sleep(args.pause)

    print(f"Selesai. Data ditulis ke {csv_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nDibatalkan oleh pengguna.")
        raise SystemExit(130)
