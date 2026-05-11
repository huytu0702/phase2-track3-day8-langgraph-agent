from pathlib import Path

from langgraph.types import Command

from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.state import Route, Scenario, initial_state


def invoke_graph(db_path: Path, scenario: Scenario, thread_id: str) -> dict:
    graph = build_graph(checkpointer=build_checkpointer("sqlite", str(db_path)))
    state = {**initial_state(scenario), "thread_id": thread_id}

    return graph.invoke(state, config={"configurable": {"thread_id": thread_id}})


def test_build_checkpointer_sqlite_creates_database(tmp_path: Path) -> None:
    db_path = tmp_path / "checkpoints.sqlite"
    scenario = Scenario(
        id="sqlite", query="How do I reset my password?", expected_route=Route.SIMPLE
    )

    result = invoke_graph(db_path, scenario, "sqlite-thread")

    assert db_path.exists()
    assert result["final_answer"]


def test_sqlite_checkpoint_keeps_event_history_across_graph_rebuild(tmp_path: Path) -> None:
    db_path = tmp_path / "checkpoints.sqlite"
    thread_id = "history-thread"
    scenario = Scenario(
        id="sqlite-history",
        query="Payment gateway unavailable during account verification",
        expected_route=Route.ERROR,
        should_retry=True,
        max_attempts=3,
        tags=["error", "retry", "unavailable"],
    )

    first = invoke_graph(db_path, scenario, thread_id)
    second = build_graph(checkpointer=build_checkpointer("sqlite", str(db_path))).get_state(
        {"configurable": {"thread_id": thread_id}}
    )

    assert second.values["events"] == first["events"]


def test_graph_can_resume_interrupted_thread_from_sqlite(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LANGGRAPH_INTERRUPT", "true")
    db_path = tmp_path / "checkpoints.sqlite"
    thread_id = "resume-thread"
    scenario = Scenario(
        id="risky-resume",
        query="Refund customer account after supervisor approval",
        expected_route=Route.RISKY,
        requires_approval=True,
        tags=["risky", "hitl", "checkpoint"],
    )
    graph = build_graph(checkpointer=build_checkpointer("sqlite", str(db_path)))
    state = {**initial_state(scenario), "thread_id": thread_id}
    config = {"configurable": {"thread_id": thread_id}}

    interrupted = graph.invoke(state, config=config)
    assert "__interrupt__" in interrupted

    rebuilt_graph = build_graph(checkpointer=build_checkpointer("sqlite", str(db_path)))
    resumed = rebuilt_graph.invoke(
        Command(resume={"approved": True, "reviewer": "tester", "comment": "ok"}),
        config=config,
    )

    assert resumed["approval"]["approved"] is True
    assert resumed["final_answer"]
