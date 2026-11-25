"""Hasilkan tabel Markdown Bab 5 dari ``results/summary.csv``.

Pemakaian:
    python -m analysis.make_tables
    python -m analysis.make_tables --out results/tables.md

Angka diformat dengan koma desimal agar konsisten dengan laporan berbahasa
Indonesia. Keluaran hanya berisi tabel; prosa Bab 5 tetap diedit manual.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

GENERAL_GRID = {(nodes, difficulty) for nodes in (2, 4) for difficulty in (1, 2, 3, 4)}

MACHINE_ORDER = ["kibar", "dzikra"]
MACHINE_LABEL = {"kibar": "Kibar", "dzikra": "Dzikra"}


# ---------------------------------------------------------------- formatting


def fmt(value: float, digits: int = 2) -> str:
    """Format angka dengan koma desimal; ``NaN`` menjadi tanda pisah."""
    if pd.isna(value):
        return "—"
    return f"{float(value):.{digits}f}".replace(".", ",")


def fmt_pm(mean: float, std: float, digits: int = 2) -> str:
    """Format ``mean ± std``."""
    if pd.isna(mean):
        return "—"
    if pd.isna(std):
        std = 0.0
    return f"{fmt(mean, digits)} ± {fmt(std, digits)}"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def _machines(summary: pd.DataFrame) -> list[str]:
    present = set(summary["machine"])
    ordered = [machine for machine in MACHINE_ORDER if machine in present]
    return ordered + sorted(present - set(ordered))


def _label(machine: str) -> str:
    return MACHINE_LABEL.get(machine, machine)


def _sorted(subset: pd.DataFrame) -> pd.DataFrame:
    return subset.sort_values(["nodes", "difficulty"])


# -------------------------------------------------------------------- tables


def tabel_grid_umum(summary: pd.DataFrame) -> str:
    headers = [
        "Mesin",
        "Node",
        "d",
        "Throughput (blok/dtk)",
        "Waktu/blok (dtk)",
        "Latensi (ms)",
        "Fork",
        "Orphan",
        "Gagal",
    ]
    rows: list[list[str]] = []

    for machine in _machines(summary):
        subset = summary[summary["machine"] == machine]
        subset = subset[
            [
                (int(nodes), int(difficulty)) in GENERAL_GRID
                for nodes, difficulty in zip(subset["nodes"], subset["difficulty"])
            ]
        ]
        for _, row in _sorted(subset).iterrows():
            rows.append(
                [
                    _label(machine),
                    str(int(row["nodes"])),
                    str(int(row["difficulty"])),
                    fmt_pm(row["throughput_bps_mean"], row["throughput_bps_std"]),
                    fmt(row["avg_block_time_s_mean"], 3),
                    fmt(row["avg_sync_latency_ms_mean"], 2),
                    fmt(row["forks_detected_mean"], 2),
                    fmt(row["orphan_blocks_mean"], 2),
                    str(int(row["timeouts"])),
                ]
            )

    return _table(headers, rows) if rows else "_Belum ada data grid umum._"


def tabel_grid_tambahan(summary: pd.DataFrame) -> str:
    headers = [
        "Mesin",
        "Node",
        "d",
        "Throughput (blok/dtk)",
        "Waktu/blok (dtk)",
        "Latensi (ms)",
        "Fork",
        "Orphan",
        "CPU (%)",
    ]
    rows: list[list[str]] = []

    for machine in _machines(summary):
        subset = summary[summary["machine"] == machine]
        subset = subset[
            [
                (int(nodes), int(difficulty)) not in GENERAL_GRID
                for nodes, difficulty in zip(subset["nodes"], subset["difficulty"])
            ]
        ]
        for _, row in _sorted(subset).iterrows():
            rows.append(
                [
                    _label(machine),
                    str(int(row["nodes"])),
                    str(int(row["difficulty"])),
                    fmt_pm(row["throughput_bps_mean"], row["throughput_bps_std"]),
                    fmt(row["avg_block_time_s_mean"], 3),
                    fmt(row["avg_sync_latency_ms_mean"], 2),
                    fmt(row["forks_detected_mean"], 2),
                    fmt(row["orphan_blocks_mean"], 2),
                    fmt(row["cpu_avg_pct_mean"], 1),
                ]
            )

    return _table(headers, rows) if rows else "_Belum ada data grid tambahan._"


def tabel_rasio(summary: pd.DataFrame) -> str:
    machines = _machines(summary)
    if len(machines) < 2:
        return "_Perbandingan mesin memerlukan data dari minimal dua mesin._"

    pivot = summary.pivot_table(
        index=["nodes", "difficulty"],
        columns="machine",
        values="throughput_bps_mean",
    ).dropna()
    if pivot.empty or "kibar" not in pivot.columns or "dzikra" not in pivot.columns:
        return "_Belum ada kombinasi grid yang sama untuk Kibar dan Dzikra._"

    headers = [
        "Node",
        "d",
        "Kibar (blok/dtk)",
        "Dzikra (blok/dtk)",
        "Rasio Dzikra/Kibar",
    ]
    rows = []
    for (nodes, difficulty), row in pivot.sort_index().iterrows():
        rows.append(
            [
                str(int(nodes)),
                str(int(difficulty)),
                fmt(row["kibar"], 2),
                fmt(row["dzikra"], 2),
                fmt(row["dzikra"] / row["kibar"], 2),
            ]
        )
    return _table(headers, rows)


def tabel_energi(summary: pd.DataFrame) -> str:
    headers = [
        "Mesin",
        "Node",
        "d",
        "CPU (%)",
        "CPU-detik",
        "Throughput (blok/dtk)",
    ]
    rows: list[list[str]] = []

    for machine in _machines(summary):
        subset = summary[summary["machine"] == machine]
        for _, row in _sorted(subset).iterrows():
            rows.append(
                [
                    _label(machine),
                    str(int(row["nodes"])),
                    str(int(row["difficulty"])),
                    fmt(row["cpu_avg_pct_mean"], 2),
                    fmt(row["cpu_seconds_proxy"], 2),
                    fmt(row["throughput_bps_mean"], 2),
                ]
            )

    return _table(headers, rows) if rows else "_Belum ada data energi._"


# ----------------------------------------------------------------------- CLI


def build_markdown(summary: pd.DataFrame) -> str:
    """Susun seluruh tabel menjadi satu dokumen Markdown."""
    summary = summary.copy()
    # Toleransi terhadap summary.csv lama yang belum punya kolom turunan.
    if "timeouts" not in summary.columns:
        summary["timeouts"] = 0
    if "cpu_seconds_proxy" not in summary.columns:
        summary["cpu_seconds_proxy"] = float("nan")

    sections = [
        ("Tabel A — Grid Umum", tabel_grid_umum(summary)),
        ("Tabel B — Grid Tambahan", tabel_grid_tambahan(summary)),
        ("Tabel C — Rasio Throughput Dzikra terhadap Kibar", tabel_rasio(summary)),
        ("Tabel D — CPU dan Proksi Energi", tabel_energi(summary)),
    ]
    body = "\n\n".join(f"### {title}\n\n{table}" for title, table in sections)
    return (
        "<!-- Dihasilkan oleh analysis/make_tables.py; jangan diedit manual. -->\n\n"
        f"{body}\n"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cetak tabel Markdown Bab 5 dari summary.csv."
    )
    parser.add_argument(
        "--summary",
        default="results/summary.csv",
        help="Path CSV ringkasan (default: results/summary.csv).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Simpan ke file (mis. results/tables.md); default cetak ke terminal.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    path = Path(args.summary)
    if not path.exists():
        raise SystemExit(
            f"{path} tidak ditemukan. Jalankan analysis.analyze lebih dulu."
        )

    summary = pd.read_csv(path)
    markdown = build_markdown(summary)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")
        print(f"Tabel ditulis ke {out}")
    else:
        print(markdown)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
