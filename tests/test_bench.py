"""Test runner benchmark tanpa membutuhkan ``node/`` asli.

Memakai ``tests/fake_node.py`` sebagai pengganti node, sehingga runner dapat
diuji penuh (spawn proses, timeout, CSV) sebelum implementasi Kibar tersedia.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import pytest

from analysis import analyze
from bench import run_experiments as bench

REPO_ROOT = Path(bench.__file__).resolve().parent.parent
FAKE_MODULE = "tests.fake_node"


def run_args(**overrides) -> argparse.Namespace:
    base = {
        "machine": "dzikra",
        "nodes": [2],
        "difficulty": [1],
        "blocks": 10,
        "runs": 1,
        "timeout": 60.0,
        "pause": 0.0,
        "out_dir": "results/raw",
        "node_module": FAKE_MODULE,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


# ------------------------------------------------------------------ int_list


def test_int_list_parses_comma_separated_values():
    assert bench.int_list("2, 4,8") == [2, 4, 8]
    assert bench.int_list("3") == [3]


def test_int_list_rejects_empty_and_non_integer():
    with pytest.raises(argparse.ArgumentTypeError):
        bench.int_list(" , ")
    with pytest.raises(argparse.ArgumentTypeError):
        bench.int_list("2,abc")


# --------------------------------------------------------------- validate_args


def test_validate_args_accepts_valid_configuration():
    bench.validate_args(run_args())  # tidak boleh melempar


@pytest.mark.parametrize("nodes", [[0], [9], [2, 9]])
def test_validate_args_rejects_out_of_range_nodes(nodes):
    with pytest.raises(SystemExit):
        bench.validate_args(run_args(nodes=nodes))


@pytest.mark.parametrize("difficulty", [[6], [-1]])
def test_validate_args_rejects_out_of_range_difficulty(difficulty):
    with pytest.raises(SystemExit):
        bench.validate_args(run_args(difficulty=difficulty))


@pytest.mark.parametrize(
    "overrides",
    [
        {"blocks": 0},
        {"runs": 0},
        {"timeout": 0},
        {"pause": -1},
    ],
)
def test_validate_args_rejects_invalid_scalars(overrides):
    with pytest.raises(SystemExit):
        bench.validate_args(run_args(**overrides))


def test_validate_args_rejects_missing_node_module():
    with pytest.raises(SystemExit):
        bench.validate_args(run_args(node_module="modul_node_tidak_ada_xyz"))


def test_validate_args_warns_for_kibar_with_more_than_four_nodes(capsys):
    bench.validate_args(run_args(machine="kibar", nodes=[8]))

    assert "Kibar" in capsys.readouterr().out


# ---------------------------------------------------------------- read_events


def test_read_events_skips_blank_and_broken_lines(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"event": "block_mined", "index": 1}',
                "",
                "bukan json",
                "[1, 2, 3]",  # JSON valid tapi bukan objek
                '{"event": "fork_detected", "index": 2}',
            ]
        ),
        encoding="utf-8",
    )

    events = bench.read_events(path)

    assert [event["event"] for event in events] == [
        "block_mined",
        "fork_detected",
    ]


def test_read_events_returns_empty_for_missing_file(tmp_path):
    assert bench.read_events(tmp_path / "tidak_ada.jsonl") == []


# ------------------------------------------------------------- compute_metrics


def test_compute_metrics_counts_blocks_latency_forks_and_orphans():
    events = [
        {"event": "block_mined", "index": 1},
        {"event": "block_mined", "index": 1},  # blok yatim (index sama)
        {"event": "block_mined", "index": 2},
        {"event": "block_received", "index": 2, "t": 1000.010, "sent_at": 1000.0},
        {"event": "block_received", "index": 2, "t": 2000.020, "sent_at": 2000.0},
        {"event": "fork_detected", "index": 2},
        {"event": "fork_detected", "index": 3},
    ]

    metrics = bench.compute_metrics(events, total_time_s=2.0, cpu_avg_pct=37.5)

    assert metrics["blocks_confirmed"] == 2
    assert metrics["forks_detected"] == 2
    assert metrics["orphan_blocks"] == 1  # 3 blok ditambang, 2 terkonfirmasi
    assert metrics["avg_sync_latency_ms"] == pytest.approx(15.0)
    assert metrics["throughput_bps"] == pytest.approx(1.0)
    assert metrics["avg_block_time_s"] == pytest.approx(1.0)
    assert metrics["cpu_avg_pct"] == pytest.approx(37.5)


def test_compute_metrics_handles_empty_and_malformed_events():
    events = [
        {"event": "block_mined", "index": "x"},  # index tidak valid -> 0
        {"event": "block_received", "index": 1, "t": 5.0},  # tanpa sent_at
        {"event": "lain"},
    ]

    metrics = bench.compute_metrics(events, total_time_s=0.0, cpu_avg_pct=-5.0)

    assert metrics["blocks_confirmed"] == 1
    assert metrics["avg_sync_latency_ms"] == 0.0
    assert metrics["throughput_bps"] == 0.0
    assert metrics["avg_block_time_s"] == 0.0
    assert metrics["cpu_avg_pct"] == 0.0  # dijepit ke rentang 0..100


def test_compute_metrics_clamps_cpu_above_hundred():
    metrics = bench.compute_metrics([], total_time_s=1.0, cpu_avg_pct=250.0)

    assert metrics["blocks_confirmed"] == 0
    assert metrics["orphan_blocks"] == 0
    assert metrics["cpu_avg_pct"] == 100.0


# ------------------------------------------------------------- build_command


def test_build_command_matches_node_contract(tmp_path):
    command = bench.build_command(
        FAKE_MODULE,
        node_id=3,
        port=5003,
        peers=[5000, 5001],
        difficulty=2,
        blocks=10,
        log_path=tmp_path / "node3.jsonl",
    )

    assert command[:3] == [command[0], "-m", FAKE_MODULE]
    assert command[command.index("--id") + 1] == "3"
    assert command[command.index("--port") + 1] == "5003"
    assert command[command.index("--peers") + 1] == "5000,5001"
    assert command[command.index("--difficulty") + 1] == "2"
    assert command[command.index("--blocks") + 1] == "10"
    assert command[command.index("--log") + 1].endswith("node3.jsonl")


# ------------------------------------------------------------------- run_once


def test_run_once_with_fake_node(tmp_path):
    row = bench.run_once(
        machine="dzikra",
        run_id=1,
        nodes=2,
        difficulty=1,
        blocks=3,
        timeout=60.0,
        node_module=FAKE_MODULE,
        out_dir=tmp_path,
        repo_root=REPO_ROOT,
    )

    assert row["status"] == "ok"
    assert row["blocks_confirmed"] == 3
    assert row["blocks_target"] == 3
    assert row["forks_detected"] >= 1
    assert row["avg_sync_latency_ms"] == pytest.approx(10.0, abs=0.5)
    assert row["orphan_blocks"] == 0
    assert row["total_time_s"] > 0
    assert 0.0 <= row["cpu_avg_pct"] <= 100.0
    assert list(row).count("status") == 1
    assert set(bench.CSV_COLUMNS) <= set(row)


def test_run_once_marks_timeout_and_kills_process(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_NODE_SLEEP", "30")

    row = bench.run_once(
        machine="dzikra",
        run_id=1,
        nodes=2,
        difficulty=1,
        blocks=3,
        timeout=1.0,
        node_module=FAKE_MODULE,
        out_dir=tmp_path,
        repo_root=REPO_ROOT,
    )

    assert row["status"] == "timeout"
    assert row["blocks_confirmed"] == 0
    assert row["total_time_s"] < 10.0  # proses benar-benar dihentikan


def test_run_once_marks_error_for_failing_node(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_NODE_FAIL", "1")

    row = bench.run_once(
        machine="dzikra",
        run_id=1,
        nodes=1,
        difficulty=1,
        blocks=2,
        timeout=60.0,
        node_module=FAKE_MODULE,
        out_dir=tmp_path,
        repo_root=REPO_ROOT,
    )

    assert row["status"] == "error"
    assert row["blocks_confirmed"] == 0


# ----------------------------------------------------------------------- CLI


def test_main_end_to_end_writes_contract_csv(tmp_path):
    out_dir = tmp_path / "raw"

    code = bench.main(
        [
            "--machine",
            "dzikra",
            "--nodes",
            "2",
            "--difficulty",
            "1",
            "--blocks",
            "2",
            "--runs",
            "1",
            "--timeout",
            "60",
            "--pause",
            "0",
            "--out-dir",
            str(out_dir),
            "--node-module",
            FAKE_MODULE,
        ]
    )

    assert code == 0
    csv_files = list(out_dir.glob("dzikra_*.csv"))
    assert len(csv_files) == 1

    data = pd.read_csv(csv_files[0])
    assert list(data.columns) == bench.CSV_COLUMNS
    assert len(data) == 1
    assert data.loc[0, "status"] == "ok"
    assert data.loc[0, "blocks_confirmed"] == 2

    # CSV harus bisa langsung dikonsumsi pipeline analisis.
    loaded = analyze.load_runs(out_dir)
    assert len(loaded) == 1
    assert loaded.loc[0, "machine"] == "dzikra"
    assert not bool(loaded.loc[0, "_is_timeout"])

    # Log per node terpisah dan folder log ada di dalam out-dir.
    logs = list((out_dir / "logs").glob("*.jsonl"))
    assert len(logs) == 2
