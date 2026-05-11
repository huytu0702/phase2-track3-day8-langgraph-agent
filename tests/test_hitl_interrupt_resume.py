from langgraph.types import Command

from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.state import Route, Scenario, initial_state


def risky_state(thread_id: str) -> dict:
    scenario = Scenario(
        id="hitl",
        query="Refund this customer and send confirmation email",
        expected_route=Route.RISKY,
        requires_approval=True,
        tags=["risky", "hitl"],
    )
    return {**initial_state(scenario), "thread_id": thread_id}


def event_nodes(state: dict) -> list[str]:
    return [event["node"] for event in state.get("events", [])]


def test_risky_route_interrupts_before_tool_when_human_required(monkeypatch) -> None:
    monkeypatch.setenv("LANGGRAPH_INTERRUPT", "true")
    graph = build_graph(checkpointer=build_checkpointer("memory"))
    thread_id = "hitl-interrupt"

    result = graph.invoke(risky_state(thread_id), config={"configurable": {"thread_id": thread_id}})
    checkpoint = graph.get_state({"configurable": {"thread_id": thread_id}})

    assert "__interrupt__" in result
    assert checkpoint.values["proposed_action"]
    assert "tool" not in event_nodes(checkpoint.values)


def test_resume_with_approve_true_continues_to_tool_and_finalizes(monkeypatch) -> None:
    monkeypatch.setenv("LANGGRAPH_INTERRUPT", "true")
    graph = build_graph(checkpointer=build_checkpointer("memory"))
    thread_id = "hitl-approve"
    config = {"configurable": {"thread_id": thread_id}}

    graph.invoke(risky_state(thread_id), config=config)
    result = graph.invoke(
        Command(resume={"approved": True, "reviewer": "tester", "comment": "approved"}),
        config=config,
    )

    assert result["approval"]["approved"] is True
    assert "tool" in event_nodes(result)
    assert "finalize" in event_nodes(result)


def test_resume_with_approve_false_routes_to_clarify(monkeypatch) -> None:
    monkeypatch.setenv("LANGGRAPH_INTERRUPT", "true")
    graph = build_graph(checkpointer=build_checkpointer("memory"))
    thread_id = "hitl-reject"
    config = {"configurable": {"thread_id": thread_id}}

    graph.invoke(risky_state(thread_id), config=config)
    result = graph.invoke(
        Command(resume={"approved": False, "reviewer": "tester", "comment": "missing evidence"}),
        config=config,
    )

    assert result["approval"]["approved"] is False
    assert "clarify" in event_nodes(result)
    assert result["pending_question"]


def test_no_auto_approval_when_interrupt_mode_enabled(monkeypatch) -> None:
    monkeypatch.setenv("LANGGRAPH_INTERRUPT", "true")
    graph = build_graph(checkpointer=build_checkpointer("memory"))
    thread_id = "hitl-no-auto"

    graph.invoke(risky_state(thread_id), config={"configurable": {"thread_id": thread_id}})
    checkpoint = graph.get_state({"configurable": {"thread_id": thread_id}})

    assert checkpoint.values.get("approval") is None
