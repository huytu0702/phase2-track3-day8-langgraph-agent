from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from langgraph.types import Command

from .graph import build_graph
from .metrics import MetricsReport, ScenarioMetric, metric_from_state, summarize_metrics
from .persistence import build_checkpointer
from .scenarios import load_scenarios
from .state import Scenario, initial_state


@dataclass(frozen=True)
class ScenarioRunResult:
    scenario: Scenario
    state: dict[str, Any]
    metric: ScenarioMetric
    interrupted: bool = False


def run_scenario(
    scenario: Scenario,
    *,
    checkpointer_kind: str = "memory",
    database_url: str | None = None,
    thread_id: str | None = None,
) -> ScenarioRunResult:
    graph = build_graph(checkpointer=build_checkpointer(checkpointer_kind, database_url))
    run_thread_id = thread_id or f"thread-{scenario.id}"
    state = {**initial_state(scenario), "thread_id": run_thread_id}
    config = {"configurable": {"thread_id": run_thread_id}}
    result = graph.invoke(state, config=config)
    interrupted = "__interrupt__" in result
    metric_state = graph.get_state(config).values if interrupted else result
    metric = metric_from_state(
        metric_state, scenario.expected_route.value, scenario.requires_approval
    )
    return ScenarioRunResult(
        scenario=scenario, state=metric_state, metric=metric, interrupted=interrupted
    )


def run_scenario_by_id(
    scenario_id: str,
    *,
    scenarios_path: Path,
    checkpointer_kind: str = "memory",
    database_url: str | None = None,
    thread_id: str | None = None,
) -> ScenarioRunResult:
    scenarios = load_scenarios(scenarios_path)
    for scenario in scenarios:
        if scenario.id == scenario_id:
            return run_scenario(
                scenario,
                checkpointer_kind=checkpointer_kind,
                database_url=database_url,
                thread_id=thread_id,
            )
    raise ValueError(f"Unknown scenario id: {scenario_id}")


def run_scenarios(
    *,
    scenarios_path: Path,
    checkpointer_kind: str = "memory",
    database_url: str | None = None,
    include_hitl: bool = False,
) -> MetricsReport:
    scenarios = load_scenarios(scenarios_path)
    metrics: list[ScenarioMetric] = []
    for scenario in scenarios:
        if scenario.requires_approval and not include_hitl:
            continue
        try:
            result = run_scenario(
                scenario,
                checkpointer_kind=checkpointer_kind,
                database_url=database_url,
                thread_id=f"batch-{scenario.id}-{uuid4().hex[:8]}",
            )
            metrics.append(result.metric)
        except Exception as exc:
            metrics.append(
                ScenarioMetric(
                    scenario_id=scenario.id,
                    success=False,
                    expected_route=scenario.expected_route.value,
                    approval_required=scenario.requires_approval,
                    errors=[str(exc)],
                )
            )
    return summarize_metrics(metrics)


def resume_thread(
    *,
    thread_id: str,
    approval: dict[str, Any],
    checkpointer_kind: str = "memory",
    database_url: str | None = None,
) -> dict[str, Any]:
    graph = build_graph(checkpointer=build_checkpointer(checkpointer_kind, database_url))
    return graph.invoke(Command(resume=approval), config={"configurable": {"thread_id": thread_id}})
