"""Analisis CSV benchmark: ringkasan statistik + grafik PNG (kontrak 6.6).

Pemakaian:
    python -m analysis.analyze                          # results/raw -> results/figures
    python -m analysis.analyze --raw-dir results/dummy  # data simulasi awal

Keluaran:
- ``results/summary.csv``: rata-rata + standar deviasi per
  ``(machine, nodes, difficulty)``.
- ``results/figures/*.png``: enam grafik berlabel Bahasa Indonesia.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # backend non-interaktif; aman di server/CI
import matplotlib.pyplot as plt
import pandas as pd

REQUIRED_COLUMNS = [
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

NUMERIC_COLUMNS = [
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

METRICS = [
    "blocks_confirmed",
    "total_time_s",
    "throughput_bps",
    "avg_block_time_s",
    "avg_sync_latency_ms",
    "forks_detected",
    "orphan_blocks",
    "cpu_avg_pct",
]

MACHINE_LABEL = {
    "kibar": "Kibar (i5-6200U, 2C/4T)",
    "dzikra": "Dzikra (i3-N305, 8C)",
}

MACHINE_ORDER = ["kibar", "dzikra"]


# --------------------------------------------------------------------- data


def load_runs(raw_dir: Path) -> pd.DataFrame:
    """Baca dan gabungkan semua CSV di ``raw_dir``."""
    files = sorted(raw_dir.glob("*.csv"))
    if not files:
        raise SystemExit(
            f"Tidak ada CSV di {raw_dir}. Jalankan benchmark atau "
            "`python -m analysis.make_dummy` lebih dulu."
        )

    frames: list[pd.DataFrame] = []
    for path in files:
        frame = pd.read_csv(path)
        missing = [col for col in REQUIRED_COLUMNS if col not in frame.columns]
        if missing:
            print(f"[lewati] {path.name}: kolom hilang {', '.join(missing)}")
            continue
        frame["source_file"] = path.name
        frames.append(frame)

    if not frames:
        raise SystemExit(f"Tidak ada CSV valid di {raw_dir}.")

    data = pd.concat(frames, ignore_index=True)
    for column in NUMERIC_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    data["machine"] = data["machine"].astype(str).str.strip().str.lower()
    data = data.dropna(subset=["machine", "nodes", "difficulty", "run_id"])

    for column in (
        "run_id",
        "nodes",
        "difficulty",
        "blocks_target",
        "blocks_confirmed",
        "forks_detected",
        "orphan_blocks",
    ):
        data[column] = data[column].astype(int)

    return data


def summarize(data: pd.DataFrame) -> pd.DataFrame:
    """Rata-rata dan standar deviasi per (machine, nodes, difficulty)."""
    grouped = data.groupby(["machine", "nodes", "difficulty"], as_index=False)

    aggregations: dict[str, tuple[str, str]] = {}
    for metric in METRICS:
        aggregations[f"{metric}_mean"] = (metric, "mean")
        aggregations[f"{metric}_std"] = (metric, "std")
    aggregations["runs"] = ("run_id", "count")

    summary = grouped.agg(**aggregations)
    summary = summary.sort_values(["machine", "nodes", "difficulty"])
    summary = summary.reset_index(drop=True)

    std_columns = [f"{metric}_std" for metric in METRICS]
    summary[std_columns] = summary[std_columns].fillna(0.0)

    # Proksi energi: persentase CPU sistem x durasi run (CPU-detik).
    # Berguna untuk mendiskusikan konsumsi energi PoW.
    summary["cpu_seconds_proxy"] = (
        summary["cpu_avg_pct_mean"] / 100.0 * summary["total_time_s_mean"]
    )
    return summary


def print_summary(summary: pd.DataFrame) -> None:
    """Cetak tabel ringkas yang nyaman dibaca di terminal."""
    columns = [
        "machine",
        "nodes",
        "difficulty",
        "runs",
        "throughput_bps_mean",
        "avg_block_time_s_mean",
        "avg_sync_latency_ms_mean",
        "forks_detected_mean",
        "orphan_blocks_mean",
        "cpu_avg_pct_mean",
    ]
    table = summary[columns].copy()
    table.columns = [
        "machine",
        "node",
        "diff",
        "run",
        "throughput (blok/dtk)",
        "waktu/blok (dtk)",
        "latensi (ms)",
        "fork",
        "orphan",
        "CPU (%)",
    ]

    print("\n=== Ringkasan rata-rata per (machine, node, difficulty) ===\n")
    for machine, group in table.groupby("machine", sort=False):
        print(f"[{machine}]")
        print(group.drop(columns=["machine"]).round(3).to_string(index=False))
        print()

    machines = set(summary["machine"])
    if {"kibar", "dzikra"} <= machines:
        pivot = summary.pivot_table(
            index=["nodes", "difficulty"],
            columns="machine",
            values="throughput_bps_mean",
        ).dropna()
        if not pivot.empty:
            pivot = pivot.assign(rasio_dzikra_per_kibar=pivot["dzikra"] / pivot["kibar"])
            print("=== Throughput Dzikra relatif terhadap Kibar (grid umum) ===\n")
            print(pivot.round(3).to_string())
            print()


# ------------------------------------------------------------------ figures


def _machine_order(summary: pd.DataFrame) -> list[str]:
    present = set(summary["machine"])
    ordered = [machine for machine in MACHINE_ORDER if machine in present]
    return ordered + sorted(present - set(ordered))


def _faceted_figure(
    summary: pd.DataFrame,
    filename: str,
    suptitle: str,
    plot_one,
    figures_dir: Path,
) -> Path:
    """Satu subplot per mesin, sumbu Y/legenda diatur oleh ``plot_one``."""
    machines = _machine_order(summary)
    fig, axes = plt.subplots(
        1, len(machines), figsize=(6.2 * len(machines), 4.6), squeeze=False
    )

    for ax, machine in zip(axes[0], machines):
        subset = summary[summary["machine"] == machine]
        plot_one(ax, subset)
        ax.set_title(MACHINE_LABEL.get(machine, machine), fontsize=11)
        ax.grid(True, alpha=0.3)
        ax.legend(title=None, fontsize=9)

    fig.suptitle(suptitle, fontsize=13)
    fig.tight_layout()
    path = figures_dir / filename
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _node_series(pivot: pd.DataFrame) -> pd.DataFrame:
    pivot = pivot.copy()
    pivot.columns = [f"{int(node)} node" for node in pivot.columns]
    return pivot


def _difficulty_series(pivot: pd.DataFrame) -> pd.DataFrame:
    pivot = pivot.copy()
    pivot.columns = [f"difficulty {int(diff)}" for diff in pivot.columns]
    return pivot


def figure_block_time(summary: pd.DataFrame, figures_dir: Path) -> Path:
    # Skala log dipakai untuk semua subplot bila rentang antar-difficulty besar,
    # agar kedua panel mudah dibandingkan.
    positive = summary["avg_block_time_s_mean"].to_numpy()
    positive = positive[positive > 0]
    use_log = len(positive) >= 2 and positive.max() / positive.min() >= 30

    def plot(ax, subset):
        pivot = subset.pivot_table(
            index="difficulty", columns="nodes", values="avg_block_time_s_mean"
        )
        pivot = _node_series(pivot)
        pivot.plot(ax=ax, marker="o")
        ax.set_xlabel("Difficulty")
        ax.set_ylabel("Waktu per blok (detik)")
        ax.set_xticks(sorted(subset["difficulty"].unique()))
        if use_log:
            ax.set_yscale("log")
            ax.set_ylabel("Waktu per blok (detik, skala log)")
        else:
            ax.set_ylim(bottom=0)

    return _faceted_figure(
        summary,
        "fig1_waktu_blok_vs_difficulty.png",
        "Waktu per Blok vs Difficulty untuk Tiap Jumlah Node",
        plot,
        figures_dir,
    )


def figure_throughput(summary: pd.DataFrame, figures_dir: Path) -> Path:
    def plot(ax, subset):
        pivot = subset.pivot_table(
            index="nodes", columns="difficulty", values="throughput_bps_mean"
        )
        _difficulty_series(pivot).plot(ax=ax, marker="o")
        ax.set_xlabel("Jumlah node")
        ax.set_ylabel("Throughput (blok/detik)")
        ax.set_xticks(sorted(subset["nodes"].unique()))
        ax.set_ylim(bottom=0)

    return _faceted_figure(
        summary,
        "fig2_throughput_vs_nodes.png",
        "Throughput vs Jumlah Node untuk Tiap Difficulty",
        plot,
        figures_dir,
    )


def figure_latency(summary: pd.DataFrame, figures_dir: Path) -> Path:
    def plot(ax, subset):
        pivot = subset.pivot_table(
            index="nodes", columns="difficulty", values="avg_sync_latency_ms_mean"
        )
        _difficulty_series(pivot).plot(ax=ax, marker="o")
        ax.set_xlabel("Jumlah node")
        ax.set_ylabel("Latensi sinkronisasi (ms)")
        ax.set_xticks(sorted(subset["nodes"].unique()))
        ax.set_ylim(bottom=0)

    return _faceted_figure(
        summary,
        "fig3_latensi_vs_nodes.png",
        "Latensi Sinkronisasi vs Jumlah Node",
        plot,
        figures_dir,
    )


def figure_forks(summary: pd.DataFrame, figures_dir: Path) -> Path:
    def plot(ax, subset):
        table = (
            subset.groupby("nodes")[["forks_detected_mean", "orphan_blocks_mean"]]
            .mean()
            .rename(
                columns={
                    "forks_detected_mean": "Fork terdeteksi",
                    "orphan_blocks_mean": "Blok orphan",
                }
            )
        )
        table.plot.bar(ax=ax, rot=0)
        ax.set_xlabel("Jumlah node")
        ax.set_ylabel("Jumlah per run (rata-rata)")
        ax.set_ylim(bottom=0)

    return _faceted_figure(
        summary,
        "fig4_fork_orphan_vs_nodes.png",
        "Fork dan Blok Orphan vs Jumlah Node (rata-rata semua difficulty)",
        plot,
        figures_dir,
    )


def figure_machine_comparison(summary: pd.DataFrame, figures_dir: Path) -> Path:
    machines = _machine_order(summary)
    fig, ax = plt.subplots(figsize=(9.5, 4.8))

    pivot = summary.pivot_table(
        index=["nodes", "difficulty"], columns="machine", values="throughput_bps_mean"
    ).dropna()

    if pivot.empty:
        ax.text(
            0.5,
            0.5,
            "Belum ada kombinasi grid yang sama\nuntuk kedua mesin",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        ax.set_axis_off()
    else:
        pivot.index = [
            f"{int(nodes)} node, d{int(diff)}" for nodes, diff in pivot.index
        ]
        pivot = pivot[[machine for machine in machines if machine in pivot.columns]]
        pivot = pivot.rename(columns=MACHINE_LABEL)
        pivot.plot.bar(ax=ax, rot=0)
        ax.set_xlabel("Kombinasi node dan difficulty (grid umum)")
        ax.set_ylabel("Throughput (blok/detik)")
        ax.set_ylim(bottom=0)
        ax.grid(True, axis="y", alpha=0.3)
        ax.legend(fontsize=9)

    ax.set_title("Perbandingan Throughput Kibar vs Dzikra pada Grid Umum")
    fig.tight_layout()
    path = figures_dir / "fig5_kibar_vs_dzikra.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def figure_cpu(summary: pd.DataFrame, figures_dir: Path) -> Path:
    def plot(ax, subset):
        pivot = subset.pivot_table(
            index="difficulty", columns="nodes", values="cpu_avg_pct_mean"
        )
        _node_series(pivot).plot(ax=ax, marker="o")
        ax.set_xlabel("Difficulty")
        ax.set_ylabel("CPU rata-rata sistem (%)")
        ax.set_xticks(sorted(subset["difficulty"].unique()))
        ax.set_ylim(0, 100)

    return _faceted_figure(
        summary,
        "fig6_cpu_vs_difficulty.png",
        "Penggunaan CPU vs Difficulty (Aspek Konsumsi Energi)",
        plot,
        figures_dir,
    )


FIGURE_BUILDERS = [
    figure_block_time,
    figure_throughput,
    figure_latency,
    figure_forks,
    figure_machine_comparison,
    figure_cpu,
]


# ---------------------------------------------------------------------- CLI


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analisis CSV benchmark blockchain dan hasilkan grafik."
    )
    parser.add_argument(
        "--raw-dir",
        default="results/raw",
        help="Folder CSV masukan (default: results/raw).",
    )
    parser.add_argument(
        "--summary",
        default="results/summary.csv",
        help="Path CSV ringkasan (default: results/summary.csv).",
    )
    parser.add_argument(
        "--figures-dir",
        default="results/figures",
        help="Folder grafik PNG (default: results/figures).",
    )
    parser.add_argument(
        "--no-figures", action="store_true", help="Hanya tulis ringkasan CSV."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    data = load_runs(Path(args.raw_dir))
    summary = summarize(data)

    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summary_path, index=False)
    print(f"Ringkasan ditulis ke {summary_path} ({len(summary)} baris).")

    print_summary(summary)

    if args.no_figures:
        return 0

    figures_dir = Path(args.figures_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)
    for builder in FIGURE_BUILDERS:
        path = builder(summary, figures_dir)
        print(f"Grafik: {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
