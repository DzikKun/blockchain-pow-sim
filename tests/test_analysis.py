"""Smoke test pipeline analisis: dummy -> CSV -> agregasi -> grafik."""

from __future__ import annotations

import re

import pandas as pd
import pytest

from analysis import analyze, make_dummy, make_tables, microbench_core

FIGURE_NAMES = {
    "fig1_waktu_blok_vs_difficulty.png",
    "fig2_throughput_vs_nodes.png",
    "fig3_latensi_vs_nodes.png",
    "fig4_fork_orphan_vs_nodes.png",
    "fig5_kibar_vs_dzikra.png",
    "fig6_cpu_vs_difficulty.png",
}


def make_row(**overrides) -> dict:
    row = {
        "machine": "dzikra",
        "run_id": 1,
        "nodes": 2,
        "difficulty": 1,
        "blocks_target": 10,
        "blocks_confirmed": 10,
        "total_time_s": 1.0,
        "throughput_bps": 10.0,
        "avg_block_time_s": 0.1,
        "avg_sync_latency_ms": 2.0,
        "forks_detected": 0,
        "orphan_blocks": 0,
        "cpu_avg_pct": 30.0,
    }
    row.update(overrides)
    return row


def write_rows(tmp_path, rows, name: str = "data.csv", columns=None):
    frame = pd.DataFrame(rows, columns=columns or analyze.REQUIRED_COLUMNS)
    path = tmp_path / name
    frame.to_csv(path, index=False)
    return path


# ------------------------------------------------------------- make_dummy


def test_build_rows_is_deterministic_and_follows_contract():
    first = make_dummy.build_rows(["dzikra"], runs=2, blocks_target=10, seed=5)
    second = make_dummy.build_rows(["dzikra"], runs=2, blocks_target=10, seed=5)

    assert first == second
    assert set(first[0]) == set(make_dummy.COLUMNS)
    assert all(row["machine"] == "dzikra" for row in first)
    assert all(row["run_id"] in (1, 2) for row in first)

    combos = {(row["nodes"], row["difficulty"]) for row in first}
    assert (8, 5) in combos  # grid tambahan Dzikra ikut dihasilkan
    assert len(first) == len(combos) * 2


def test_write_csvs_then_load_runs(tmp_path):
    rows = make_dummy.build_rows(["kibar", "dzikra"], runs=1, blocks_target=10, seed=3)
    paths = make_dummy.write_csvs(rows, tmp_path, "20260101_000000")

    assert {path.name for path in paths} == {
        "kibar_dummy_20260101_000000.csv",
        "dzikra_dummy_20260101_000000.csv",
    }

    data = analyze.load_runs(tmp_path)

    assert len(data) == len(rows)
    assert set(data["machine"]) == {"kibar", "dzikra"}
    assert data["_is_timeout"].sum() == 0
    assert data["run_id"].dtype.kind == "i"


# ------------------------------------------------------------- agregasi


def test_summarize_computes_mean_std_and_timeouts(tmp_path):
    write_rows(
        tmp_path,
        [
            make_row(run_id=1),
            make_row(run_id=2, blocks_confirmed=5, throughput_bps=5.0),
        ],
    )

    summary = analyze.summarize(analyze.load_runs(tmp_path))

    assert len(summary) == 1
    row = summary.iloc[0]
    assert row["runs"] == 2
    assert row["timeouts"] == 1
    assert row["blocks_confirmed_mean"] == 7.5
    assert row["throughput_bps_mean"] == 7.5
    assert row["blocks_confirmed_std"] == pytest.approx(3.5355, rel=1e-3)


def test_summarize_accepts_dataframe_without_internal_column():
    data = pd.DataFrame([make_row()])

    summary = analyze.summarize(data)

    assert summary.loc[0, "runs"] == 1
    assert summary.loc[0, "timeouts"] == 0


# --------------------------------------------------------------- load_runs


def test_load_runs_skips_file_with_missing_columns(tmp_path, capsys):
    write_rows(tmp_path, [make_row()], name="good.csv")
    missing = [col for col in analyze.REQUIRED_COLUMNS if col != "cpu_avg_pct"]
    write_rows(tmp_path, [make_row()], name="rusak.csv", columns=missing)

    data = analyze.load_runs(tmp_path)

    assert len(data) == 1
    assert "rusak.csv" in capsys.readouterr().out


def test_load_runs_rejects_empty_directory(tmp_path):
    with pytest.raises(SystemExit):
        analyze.load_runs(tmp_path)


# -------------------------------------------------------------------- CLI


def test_main_can_exclude_timeouts(tmp_path, capsys):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    write_rows(
        raw_dir,
        [
            make_row(run_id=1),
            make_row(run_id=2, blocks_confirmed=4, throughput_bps=4.0),
        ],
    )
    summary_path = tmp_path / "out" / "summary.csv"

    code = analyze.main(
        [
            "--raw-dir",
            str(raw_dir),
            "--summary",
            str(summary_path),
            "--no-figures",
            "--exclude-timeouts",
        ]
    )

    assert code == 0
    capsys.readouterr()  # bersihkan output sebelum assertion berikutnya

    summary = pd.read_csv(summary_path)
    assert len(summary) == 1
    assert summary.loc[0, "runs"] == 1
    assert summary.loc[0, "timeouts"] == 0


def test_main_generates_six_figures(tmp_path):
    rows = make_dummy.build_rows(["kibar", "dzikra"], runs=1, blocks_target=10, seed=11)
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    make_dummy.write_csvs(rows, raw_dir, "20260101_000000")

    figures_dir = tmp_path / "figures"
    summary_path = tmp_path / "out" / "summary.csv"

    code = analyze.main(
        [
            "--raw-dir",
            str(raw_dir),
            "--summary",
            str(summary_path),
            "--figures-dir",
            str(figures_dir),
        ]
    )

    assert code == 0
    assert summary_path.exists()
    assert {path.name for path in figures_dir.glob("*.png")} == FIGURE_NAMES


# ---------------------------------------------------------------- tabel


def _sample_summary() -> pd.DataFrame:
    rows = make_dummy.build_rows(
        ["kibar", "dzikra"], runs=1, blocks_target=10, seed=2
    )
    return analyze.summarize(pd.DataFrame(rows))


def test_make_tables_produces_all_sections():
    markdown = make_tables.build_markdown(_sample_summary())

    assert "Tabel A — Grid Umum" in markdown
    assert "Tabel B — Grid Tambahan" in markdown
    assert "Tabel C" in markdown
    assert "Tabel D" in markdown
    assert "Kibar" in markdown and "Dzikra" in markdown
    assert "±" in markdown
    assert re.search(r"\d,\d{2}", markdown)  # desimal koma
    assert "Rasio Dzikra/Kibar" in markdown


def test_make_tables_tolerates_old_summary_without_derived_columns():
    summary = _sample_summary().drop(columns=["timeouts", "cpu_seconds_proxy"])

    markdown = make_tables.build_markdown(summary)

    assert "Tabel A" in markdown
    assert "Tabel D" in markdown


def test_make_tables_main_writes_utf8_file(tmp_path):
    summary_path = tmp_path / "summary.csv"
    _sample_summary().to_csv(summary_path, index=False)
    out_path = tmp_path / "tables.md"

    code = make_tables.main(["--summary", str(summary_path), "--out", str(out_path)])

    assert code == 0
    content = out_path.read_text(encoding="utf-8")
    assert "Tabel A — Grid Umum" in content
    assert "±" in content


# ------------------------------------------------------------ microbench


def test_measure_hash_rate_positive():
    assert microbench_core.measure_hash_rate(1000) > 0


def test_measure_sustained_returns_one_rate_per_window():
    rates = microbench_core.measure_sustained_hash_rate(1000, 2)

    assert len(rates) == 2
    assert all(rate > 0 for rate in rates)


def test_measure_difficulty_returns_valid_stats():
    result = microbench_core.measure_difficulty(
        difficulty=1, samples=1, verify_iterations=3
    )

    assert result["difficulty"] == 1
    assert result["samples"] == 1
    assert result["theory_attempts"] == 16
    assert result["avg_attempts"] >= 1
    assert result["avg_mine_time_s"] > 0
    assert result["attempts_per_sec"] > 0
    assert result["verify_us"] > 0


def test_microbench_main_writes_both_csvs(tmp_path):
    code = microbench_core.main(
        [
            "--machine",
            "test",
            "--difficulties",
            "1",
            "--samples",
            "1",
            "--hash-iterations",
            "500",
            "--verify-iterations",
            "3",
            "--sustained-windows",
            "2",
            "--sustained-iterations",
            "500",
            "--out-dir",
            str(tmp_path),
        ]
    )

    assert code == 0
    files = list(tmp_path.glob("test_microbench_*.csv"))
    assert len(files) == 2

    mining_file = next(path for path in files if "sustained" not in path.name)
    sustained_file = next(path for path in files if "sustained" in path.name)

    mining = pd.read_csv(mining_file)
    assert set(microbench_core.COLUMNS) <= set(mining.columns)
    assert len(mining) == 1

    sustained = pd.read_csv(sustained_file)
    assert len(sustained) == 2
    assert (sustained["hash_per_s"] > 0).all()


