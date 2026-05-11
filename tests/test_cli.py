import json
from pathlib import Path

from typer.testing import CliRunner

from langgraph_agent_lab.cli import app
from langgraph_agent_lab.runner import list_thread_history, run_scenario
from langgraph_agent_lab.state import Route, Scenario


def test_cli_run_scenario_outputs_metric() -> None:
    result = CliRunner().invoke(
        app,
        ["run-scenario", "--id", "S01_simple", "--thread-id", "cli-test"],
    )

    assert result.exit_code == 0
    assert '"scenario_id": "S01_simple"' in result.output


def write_config(tmp_path: Path, db_path: Path) -> Path:
    config_path = tmp_path / "lab.yaml"
    config_path.write_text(
        (
            "scenarios_path: data/sample/scenarios.jsonl\n"
            "checkpointer: sqlite\n"
            f"database_url: {db_path}\n"
        ),
        encoding="utf-8",
    )
    return config_path


def approval_checkpoint_id(history: list[dict]) -> str:
    for item in history:
        if "approval" in item["next_nodes"]:
            return str(item["checkpoint_id"])
    raise AssertionError("No approval checkpoint found")


def test_cli_validate_metrics_accepts_report(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "total_scenarios": 6,
                "success_rate": 1.0,
                "avg_nodes_visited": 1.0,
                "total_retries": 0,
                "total_interrupts": 0,
                "resume_success": False,
                "scenario_metrics": [],
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["validate-metrics", "--metrics", str(metrics_path)])

    assert result.exit_code == 0
    assert "Metrics valid" in result.output


def test_cli_history_outputs_checkpoints(tmp_path: Path) -> None:
    db_path = tmp_path / "checkpoints.sqlite"
    config_path = write_config(tmp_path, db_path)
    run_scenario(
        Scenario(id="cli-history", query="How do I reset MFA?", expected_route=Route.SIMPLE),
        checkpointer_kind="sqlite",
        database_url=str(db_path),
        thread_id="cli-history-thread",
    )

    result = CliRunner().invoke(
        app,
        ["history", "--thread-id", "cli-history-thread", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert "cli-history-thread" in result.output
    assert "checkpoint_id" in result.output


def test_cli_time_travel_forks_checkpoint(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LANGGRAPH_INTERRUPT", "true")
    db_path = tmp_path / "checkpoints.sqlite"
    config_path = write_config(tmp_path, db_path)
    source_thread_id = "cli-source"
    run_scenario(
        Scenario(
            id="cli-time-travel",
            query="Refund order 12345 after approval",
            expected_route=Route.RISKY,
            requires_approval=True,
            tags=["risky", "hitl"],
        ),
        checkpointer_kind="sqlite",
        database_url=str(db_path),
        thread_id=source_thread_id,
    )
    checkpoint_id = approval_checkpoint_id(
        list_thread_history(
            thread_id=source_thread_id,
            checkpointer_kind="sqlite",
            database_url=str(db_path),
        )
    )

    result = CliRunner().invoke(
        app,
        [
            "time-travel",
            "--source-thread-id",
            source_thread_id,
            "--checkpoint-id",
            checkpoint_id,
            "--new-thread-id",
            "cli-fork",
            "--approve",
            "false",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert '"new_thread_id": "cli-fork"' in result.output
    assert '"approved": false' in result.output
