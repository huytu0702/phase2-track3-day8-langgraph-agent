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


@dataclass(frozen=True)
class ForkResult:
    source_thread_id: str
    checkpoint_id: str
    new_thread_id: str
    state: dict[str, Any]

    def model_dump(self) -> dict[str, Any]:
        return {
            "source_thread_id": self.source_thread_id,
            "checkpoint_id": self.checkpoint_id,
            "new_thread_id": self.new_thread_id,
            "state": self.state,
        }


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


def snapshot_checkpoint_id(snapshot: Any) -> str | None:
    config = snapshot.config or {}
    configurable = config.get("configurable", {})
    checkpoint_id = configurable.get("checkpoint_id")
    return str(checkpoint_id) if checkpoint_id else None


def snapshot_parent_checkpoint_id(snapshot: Any) -> str | None:
    parent_config = snapshot.parent_config or {}
    configurable = parent_config.get("configurable", {})
    checkpoint_id = configurable.get("checkpoint_id")
    return str(checkpoint_id) if checkpoint_id else None


def event_nodes(state: dict[str, Any]) -> list[str]:
    return [str(event.get("node", "")) for event in state.get("events", [])]


def last_event_node(state: dict[str, Any]) -> str | None:
    nodes = [node for node in event_nodes(state) if node]
    return nodes[-1] if nodes else None


def list_thread_history(
    *,
    thread_id: str,
    checkpointer_kind: str = "memory",
    database_url: str | None = None,
) -> list[dict[str, Any]]:
    graph = build_graph(checkpointer=build_checkpointer(checkpointer_kind, database_url))
    config = {"configurable": {"thread_id": thread_id}}
    history: list[dict[str, Any]] = []
    for snapshot in graph.get_state_history(config):
        values = dict(snapshot.values or {})
        checkpoint_thread_id = str(values.get("thread_id") or thread_id)
        nodes = event_nodes(values)
        history.append(
            {
                "thread_id": checkpoint_thread_id,
                "checkpoint_id": snapshot_checkpoint_id(snapshot),
                "parent_checkpoint_id": snapshot_parent_checkpoint_id(snapshot),
                "scenario_id": values.get("scenario_id"),
                "route": values.get("route"),
                "next_nodes": list(snapshot.next or ()),
                "last_node": nodes[-1] if nodes else None,
                "nodes_visited": len(nodes),
                "event_count": len(values.get("events", [])),
                "has_final_answer": bool(values.get("final_answer")),
            }
        )
    return history


def find_checkpoint_snapshot(graph: Any, thread_id: str, checkpoint_id: str) -> Any:
    config = {"configurable": {"thread_id": thread_id}}
    for snapshot in graph.get_state_history(config):
        if snapshot_checkpoint_id(snapshot) == checkpoint_id:
            return snapshot
    raise ValueError(f"Unknown checkpoint id: {checkpoint_id}")


def resume_thread(
    *,
    thread_id: str,
    approval: dict[str, Any],
    checkpointer_kind: str = "memory",
    database_url: str | None = None,
) -> dict[str, Any]:
    graph = build_graph(checkpointer=build_checkpointer(checkpointer_kind, database_url))
    config = {"configurable": {"thread_id": thread_id}}
    checkpoint = graph.get_state(config)
    if "approval" not in checkpoint.next:
        raise ValueError(f"No resumable checkpoint for thread id: {thread_id}")
    return graph.invoke(Command(resume=approval), config=config)


def fork_from_checkpoint(
    *,
    source_thread_id: str,
    checkpoint_id: str,
    new_thread_id: str,
    approval: dict[str, Any] | None = None,
    checkpointer_kind: str = "memory",
    database_url: str | None = None,
) -> dict[str, Any]:
    graph = build_graph(checkpointer=build_checkpointer(checkpointer_kind, database_url))
    snapshot = find_checkpoint_snapshot(graph, source_thread_id, checkpoint_id)
    values = {**dict(snapshot.values or {}), "thread_id": new_thread_id}
    as_node = last_event_node(values)
    if as_node is None:
        raise ValueError(f"Checkpoint has no replayable state: {checkpoint_id}")

    fork_config = {"configurable": {"thread_id": new_thread_id}}
    updated_config = graph.update_state(fork_config, values, as_node=as_node)
    if approval is None:
        state = graph.get_state(updated_config).values
    else:
        state = graph.invoke(Command(resume=approval), config=updated_config)
    return ForkResult(
        source_thread_id=source_thread_id,
        checkpoint_id=checkpoint_id,
        new_thread_id=new_thread_id,
        state=state,
    ).model_dump()
