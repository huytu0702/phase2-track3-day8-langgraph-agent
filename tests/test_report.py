from pathlib import Path

from langgraph_agent_lab.metrics import metric_from_state, summarize_metrics
from langgraph_agent_lab.report import render_report_stub, write_report


def test_render_report_stub_includes_resilience_summary() -> None:
    metric = metric_from_state(
        {
            "scenario_id": "S",
            "route": "error",
            "final_answer": "ok",
            "events": [],
            "errors": [],
        },
        "error",
        False,
    )
    report = render_report_stub(summarize_metrics([metric]))

    assert "Total scenarios: 1" in report
    assert "Total retries" in report


def test_write_report_creates_parent_directory(tmp_path: Path) -> None:
    metric = metric_from_state(
        {
            "scenario_id": "S",
            "route": "simple",
            "final_answer": "ok",
            "events": [],
            "errors": [],
        },
        "simple",
        False,
    )
    output = tmp_path / "nested" / "report.md"

    write_report(summarize_metrics([metric]), output)

    assert output.exists()
    assert output.read_text(encoding="utf-8").startswith("# Day 08 Lab Report")
