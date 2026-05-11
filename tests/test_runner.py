from pathlib import Path

from langgraph_agent_lab.runner import run_scenario_by_id, run_scenarios


def test_run_scenario_by_id_returns_metric_and_state(tmp_path: Path) -> None:
    result = run_scenario_by_id(
        "S01_simple",
        scenarios_path=Path("data/sample/scenarios.jsonl"),
        checkpointer_kind="memory",
        database_url=None,
        thread_id="runner-one",
    )

    assert result.metric.success is True
    assert result.state["scenario_id"] == "S01_simple"


def test_run_scenarios_continues_when_one_scenario_requires_human_input(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("LANGGRAPH_INTERRUPT", "true")

    result = run_scenarios(
        scenarios_path=Path("data/sample/scenarios.jsonl"),
        checkpointer_kind="memory",
        database_url=None,
        include_hitl=False,
    )

    assert result.total_scenarios > 0
    assert all(not item.approval_required for item in result.scenario_metrics)
