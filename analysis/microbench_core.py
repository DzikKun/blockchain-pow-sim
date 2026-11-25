"""Microbenchmark core PoW di satu proses (pengukuran asli).

Skrip ini **bukan** bagian dari grid benchmark jaringan; tujuannya mengukur
karakter dasar mining di satu mesin:

- laju hash mentah SHA-256 + serialisasi JSON,
- waktu mining nyata untuk difficulty 1..5,
- jumlah percobaan aktual dibanding ekspektasi teori ``16^difficulty``,
- waktu verifikasi ``is_valid_pow``.

Hasil disimpan terpisah dari ``results/raw/`` agar tidak bercampur dengan CSV
kontrak benchmark 6.6.

Pemakaian:
    python -m analysis.microbench_core
    python -m analysis.microbench_core --samples 5 --difficulties 1,2,3
"""

from __future__ import annotations

import argparse
import csv
import statistics
import time
from pathlib import Path

from core import Block, MAX_DIFFICULTY, is_valid_pow, mine

COLUMNS = [
    "machine",
    "timestamp",
    "difficulty",
    "samples",
    "hash_per_s",
    "avg_mine_time_s",
    "std_mine_time_s",
    "avg_attempts",
    "theory_attempts",
    "attempts_per_sec",
    "verify_us",
]

SUSTAINED_COLUMNS = [
    "machine",
    "timestamp",
    "window",
    "iterations",
    "hash_per_s",
]


def measure_hash_rate(iterations: int) -> float:
    """Perkiraan jumlah hash (SHA-256 + JSON) per detik."""
    block = Block(
        index=1,
        timestamp=0.0,
        transactions=[{"bench": True}],
        prev_hash="0" * 64,
    )
    started = time.perf_counter()
    for nonce in range(iterations):
        block.nonce = nonce
        block.compute_hash()
    elapsed = time.perf_counter() - started
    if elapsed <= 0:
        raise RuntimeError("Durasi pengukuran hash rate tidak valid.")
    return iterations / elapsed


def measure_sustained_hash_rate(iterations: int, windows: int) -> list[float]:
    """Ukur hash rate berurutan untuk melihat penurunan akibat beban panas."""
    return [measure_hash_rate(iterations) for _ in range(windows)]


def measure_difficulty(
    difficulty: int,
    samples: int,
    verify_iterations: int,
) -> dict:
    """Ukur mining dan verifikasi untuk satu tingkat difficulty."""
    times: list[float] = []
    attempts: list[int] = []
    last_block: Block | None = None

    for sample in range(samples):
        block = Block(
            index=1,
            timestamp=float(sample),
            transactions=[{"benchmark": difficulty}],
            prev_hash="0" * 64,
        )
        started = time.perf_counter()
        mined, tries = mine(block, difficulty)
        elapsed = time.perf_counter() - started

        if mined is None or not is_valid_pow(mined, difficulty):
            raise RuntimeError(
                f"Mining difficulty {difficulty} gagal pada sampel {sample + 1}."
            )

        times.append(elapsed)
        attempts.append(tries)
        last_block = mined

    assert last_block is not None

    verify_started = time.perf_counter()
    for _ in range(verify_iterations):
        is_valid_pow(last_block, difficulty)
    verify_us = (
        (time.perf_counter() - verify_started) / verify_iterations * 1_000_000
    )

    avg_time = statistics.mean(times)
    # Laju per sampel dirata-ratakan (rasio mean attempts / mean time bias).
    rates = [tries / elapsed for tries, elapsed in zip(attempts, times)]
    return {
        "difficulty": difficulty,
        "samples": samples,
        "avg_mine_time_s": avg_time,
        "std_mine_time_s": statistics.stdev(times) if len(times) > 1 else 0.0,
        "avg_attempts": statistics.mean(attempts),
        "theory_attempts": 16 ** difficulty,
        "attempts_per_sec": statistics.mean(rates),
        "verify_us": verify_us,
    }


def print_results(
    machine: str,
    hash_per_s: float,
    hash_iterations: int,
    sustained_rates: list[float],
    sustained_iterations: int,
    rows: list[dict],
) -> None:
    print(f"Mesin            : {machine}")
    print(
        f"Hash rate mentah : {hash_per_s:,.0f} hash/detik "
        f"({hash_iterations:,} hash)"
    )
    print()

    if sustained_rates:
        print(
            "Hash rate berkelanjutan "
            f"({sustained_iterations:,} hash per jendela):"
        )
        print("| jendela | hash/dtk |")
        print("|---|---|")
        for window, rate in enumerate(sustained_rates, start=1):
            print(f"| {window} | {rate:,.0f} |")
        if len(sustained_rates) > 1 and sustained_rates[0] > 0:
            ratio = sustained_rates[-1] / sustained_rates[0]
            print(f"Rasio jendela terakhir/pertama: {ratio:.2f}")
        print()

    header = (
        "| d | sampel | rata-rata (s) | std (s) | attempts | teori 16^d "
        "| attempts/detik | verifikasi (µs) |"
    )
    print(header)
    print("|---|---|---|---|---|---|---|---|")
    for row in rows:
        print(
            f"| {row['difficulty']} | {row['samples']} "
            f"| {row['avg_mine_time_s']:.4f} "
            f"| {row['std_mine_time_s']:.4f} "
            f"| {row['avg_attempts']:.0f} "
            f"| {row['theory_attempts']:,} "
            f"| {row['attempts_per_sec']:,.0f} "
            f"| {row['verify_us']:.2f} |"
        )
    print()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Microbenchmark core PoW (satu proses)."
    )
    parser.add_argument(
        "--machine",
        default="dzikra",
        help="Label mesin untuk nama file (default: dzikra).",
    )
    parser.add_argument(
        "--samples", type=int, default=3, help="Sampel mining per difficulty."
    )
    parser.add_argument(
        "--difficulties",
        default="1,2,3,4,5",
        help="Daftar difficulty dipisah koma (default: 1,2,3,4,5).",
    )
    parser.add_argument(
        "--hash-iterations",
        type=int,
        default=20_000,
        help="Jumlah hash untuk mengukur laju mentah.",
    )
    parser.add_argument(
        "--verify-iterations",
        type=int,
        default=200,
        help="Jumlah verifikasi untuk mengukur biaya validasi.",
    )
    parser.add_argument(
        "--sustained-windows",
        type=int,
        default=5,
        help="Jumlah jendela pengukuran hash berkelanjutan (0 = lewati).",
    )
    parser.add_argument(
        "--sustained-iterations",
        type=int,
        default=200_000,
        help="Jumlah hash per jendela berkelanjutan.",
    )
    parser.add_argument(
        "--out-dir",
        default="results/microbench",
        help="Folder keluaran CSV (default: results/microbench).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    difficulties = [int(item) for item in args.difficulties.split(",") if item.strip()]
    if not difficulties:
        raise SystemExit("Daftar difficulty kosong.")
    for difficulty in difficulties:
        if not 0 <= difficulty <= MAX_DIFFICULTY:
            raise SystemExit(
                f"Difficulty {difficulty} di luar rentang 0..{MAX_DIFFICULTY}."
            )
    if args.samples < 1:
        raise SystemExit("--samples minimal 1.")
    if args.hash_iterations < 1:
        raise SystemExit("--hash-iterations minimal 1.")
    if args.sustained_windows < 0:
        raise SystemExit("--sustained-windows tidak boleh negatif.")
    if args.sustained_windows > 0 and args.sustained_iterations < 1:
        raise SystemExit("--sustained-iterations minimal 1.")

    print(f"Mengukur hash rate ({args.hash_iterations:,} hash)...")
    hash_per_s = measure_hash_rate(args.hash_iterations)

    sustained_rates: list[float] = []
    if args.sustained_windows > 0:
        print(
            "Mengukur hash rate berkelanjutan "
            f"({args.sustained_windows} x {args.sustained_iterations:,} hash)..."
        )
        sustained_rates = measure_sustained_hash_rate(
            args.sustained_iterations, args.sustained_windows
        )

    rows: list[dict] = []
    for difficulty in difficulties:
        print(f"  mining difficulty {difficulty} x {args.samples} sampel...")
        rows.append(
            measure_difficulty(
                difficulty,
                samples=args.samples,
                verify_iterations=args.verify_iterations,
            )
        )

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.machine}_microbench_{stamp}.csv"

    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "machine": args.machine,
                    "timestamp": stamp,
                    "hash_per_s": round(hash_per_s, 2),
                    **{
                        key: (round(value, 6) if isinstance(value, float) else value)
                        for key, value in row.items()
                    },
                }
            )

    print()
    print_results(
        args.machine,
        hash_per_s,
        args.hash_iterations,
        sustained_rates,
        args.sustained_iterations,
        rows,
    )
    print(f"CSV ditulis ke {out_path}")

    if sustained_rates:
        sustained_path = (
            out_dir / f"{args.machine}_microbench_sustained_{stamp}.csv"
        )
        with sustained_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=SUSTAINED_COLUMNS)
            writer.writeheader()
            for window, rate in enumerate(sustained_rates, start=1):
                writer.writerow(
                    {
                        "machine": args.machine,
                        "timestamp": stamp,
                        "window": window,
                        "iterations": args.sustained_iterations,
                        "hash_per_s": round(rate, 2),
                    }
                )
        print(f"CSV sustained ditulis ke {sustained_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
