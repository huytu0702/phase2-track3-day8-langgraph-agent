import json
from pathlib import Path

from typer.testing import CliRunner

from langgraph_agent_lab.cli import app


def test_cli_run_scenario_outputs_metric() -> None:
    result = CliRunner().invoke(
        app,
        ["run-scenario", "--id", "S01_simple", "--thread-id", "cli-test"],
    )

    assert result.exit_code == 0
    assert '"scenario_id": "S01_simple"' in result.output


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
