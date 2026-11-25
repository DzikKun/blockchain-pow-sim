"""Bangkitkan CSV hasil benchmark palsu (dummy) sesuai kontrak AGENT.md 6.6.

Tujuan: mengembangkan ``analyze.py`` dan grafik tanpa menunggu runner
``bench/`` dari Kibar. Data ini **bukan** hasil pengukuran dan disimpan
terpisah di ``results/dummy/`` agar tidak tercampur dengan ``results/raw/``.

Pemakaian:
    python -m analysis.make_dummy
    python -m analysis.make_dummy --runs 3 --out-dir results/dummy --seed 42

Kolom CSV (urutan persis kontrak 6.6):
    machine,run_id,nodes,difficulty,blocks_target,blocks_confirmed,total_time_s,
    throughput_bps,avg_block_time_s,avg_sync_latency_ms,forks_detected,
    orphan_blocks,cpu_avg_pct
"""

from __future__ import annotations

import argparse
import csv
import random
import time
from pathlib import Path

COLUMNS = [
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
]

# Grid umum (Bagian 7) + grid tambahan khusus Dzikra.
GENERAL_NODES = (2, 4)
GENERAL_DIFFICULTIES = (1, 2, 3, 4)
EXTRA_NODES = (8,)
EXTRA_DIFFICULTY = (5,)

# Faktor lambat CPU: Kibar i5-6200U (2C/4T, 2016) vs Dzikra i3-N305 (8C).
MACHINE_FACTOR = {"kibar": 1.55, "dzikra": 1.0}
# Jumlah thread logis (dipakai untuk menaksir persentase CPU sistem).
MACHINE_LOGICAL_CPUS = {"kibar": 4, "dzikra": 8}
# Perkiraan waktu satu hash SHA-256 + serialisasi JSON di Python (detik).
SECONDS_PER_HASH = 8e-6
# Batas bawah waktu blok karena overhead loop (detik).
MIN_BLOCK_SECONDS = 0.002


def experiment_grid(machine: str) -> list[tuple[int, int]]:
    """Daftar pasangan (nodes, difficulty) untuk satu mesin."""
    grid = [(n, d) for n in GENERAL_NODES for d in GENERAL_DIFFICULTIES]
    if machine == "dzikra":
        grid += [(n, d) for n in EXTRA_NODES for d in GENERAL_DIFFICULTIES]
        grid += [(n, d) for n in (2, 4, 8) for d in EXTRA_DIFFICULTY]
    return grid


def simulate_run(
    rng: random.Random,
    machine: str,
    nodes: int,
    difficulty: int,
    blocks_target: int = 10,
) -> dict:
    """Model kasar namun masuk akal untuk satu run benchmark."""
    hw = MACHINE_FACTOR[machine]

    # Ekspektasi percobaan PoW = 16^difficulty (satu karakter hex = 4 bit).
    # Hash power bertambah sublinear karena beberapa proses berebut core.
    base_block_time = max(
        MIN_BLOCK_SECONDS, (16 ** difficulty) * SECONDS_PER_HASH
    ) * hw
    hash_power = nodes ** 0.85
    fork_penalty = 1.0 + 0.03 * max(0, nodes - 1)
    mining_interval = base_block_time / hash_power * fork_penalty
    mining_interval *= rng.uniform(0.85, 1.20)

    # Overhead proses, sinkronisasi awal, dan penulisan log.
    startup = rng.uniform(0.5, 1.0) * (1.0 + 0.01 * nodes)
    total_time = blocks_target * mining_interval + startup
    blocks_confirmed = blocks_target
    throughput = blocks_confirmed / total_time
    avg_block_time = total_time / blocks_confirmed

    latency_ms = (0.8 + 0.5 * nodes + 0.5 * difficulty) * hw
    latency_ms *= rng.uniform(0.85, 1.20)

    # Fork makin sering saat banyak node dan blok ditemukan cepat (difficulty
    # rendah); makin jarang saat interval blok panjang.
    fork_mean = (nodes - 1) * 1.5 / (difficulty ** 1.2)
    forks = max(0, round(rng.gauss(fork_mean, max(0.3, fork_mean ** 0.5))))
    orphan = min(forks, max(0, round(forks * rng.uniform(0.3, 1.0))))

    # Satu node yang mining memakai ~1 core; persentase CPU sistem mengikuti
    # rasio node terhadap jumlah thread logis.
    cpu = (
        min(97.0, (nodes / MACHINE_LOGICAL_CPUS[machine]) * 90.0)
        + 6.0
        + 1.5 * difficulty
    )
    cpu = min(97.0, cpu * rng.uniform(0.92, 1.05))

    return {
        "machine": machine,
        "nodes": nodes,
        "difficulty": difficulty,
        "blocks_target": blocks_target,
        "blocks_confirmed": blocks_confirmed,
        "total_time_s": round(total_time, 3),
        "throughput_bps": round(throughput, 4),
        "avg_block_time_s": round(avg_block_time, 4),
        "avg_sync_latency_ms": round(latency_ms, 2),
        "forks_detected": forks,
        "orphan_blocks": orphan,
        "cpu_avg_pct": round(cpu, 2),
    }


def build_rows(
    machines: list[str], runs: int, blocks_target: int, seed: int
) -> list[dict]:
    rng = random.Random(seed)
    rows: list[dict] = []
    for machine in machines:
        for nodes, difficulty in experiment_grid(machine):
            for run_id in range(1, runs + 1):
                row = simulate_run(rng, machine, nodes, difficulty, blocks_target)
                row["run_id"] = run_id
                rows.append(row)
    return rows


def write_csvs(rows: list[dict], out_dir: Path, stamp: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    by_machine: dict[str, list[dict]] = {}
    for row in rows:
        by_machine.setdefault(row["machine"], []).append(row)

    written: list[Path] = []
    for machine, machine_rows in by_machine.items():
        path = out_dir / f"{machine}_dummy_{stamp}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            for row in machine_rows:
                writer.writerow({key: row[key] for key in COLUMNS})
        written.append(path)
    return written


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bangkitkan CSV dummy hasil benchmark blockchain."
    )
    parser.add_argument(
        "--machines",
        default="kibar,dzikra",
        help="Daftar mesin dipisah koma (default: kibar,dzikra).",
    )
    parser.add_argument(
        "--runs", type=int, default=3, help="Jumlah ulangan per kombinasi."
    )
    parser.add_argument(
        "--blocks", type=int, default=10, help="blocks_target per run."
    )
    parser.add_argument(
        "--out-dir",
        default="results/dummy",
        help="Folder keluaran (default: results/dummy).",
    )
    parser.add_argument("--seed", type=int, default=42, help="Seed RNG.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    machines = [m.strip() for m in args.machines.split(",") if m.strip()]
    unknown = sorted(set(machines) - set(MACHINE_FACTOR))
    if unknown:
        raise SystemExit(f"Mesin tidak dikenal: {', '.join(unknown)}")

    rows = build_rows(machines, args.runs, args.blocks, args.seed)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    paths = write_csvs(rows, Path(args.out_dir), stamp)

    print(f"Menulis {len(rows)} baris dummy ke:")
    for path in paths:
        print(f"  - {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
