from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.state import Route, Scenario, initial_state


def run_scenario(scenario: Scenario, thread_id: str) -> dict:
    graph = build_graph(checkpointer=build_checkpointer("memory"))
    state = {**initial_state(scenario), "thread_id": thread_id}

    return graph.invoke(state, config={"configurable": {"thread_id": thread_id}})


def event_nodes(state: dict) -> list[str]:
    return [event["node"] for event in state.get("events", [])]


def test_retry_path_is_deterministic_for_same_scenario_metadata() -> None:
    scenario = Scenario(
        id="retry-deterministic",
        query="Payment gateway unavailable during account verification",
        expected_route=Route.ERROR,
        should_retry=True,
        max_attempts=3,
        tags=["error", "retry", "unavailable"],
    )

    first = run_scenario(scenario, "retry-a")
    second = run_scenario(scenario, "retry-b")

    assert event_nodes(first) == event_nodes(second)
    assert first["attempt"] == second["attempt"] == 2
    assert first["evaluation_result"] == second["evaluation_result"] == "success"


def test_transient_failure_recovers_before_max_attempts() -> None:
    scenario = Scenario(
        id="transient",
        query="Order lookup service timeout while checking order 54321",
        expected_route=Route.ERROR,
        should_retry=True,
        max_attempts=3,
        tags=["error", "retry", "timeout"],
    )

    result = run_scenario(scenario, "transient")

    assert result["attempt"] == 2
    assert result["evaluation_result"] == "success"
    assert "dead_letter" not in event_nodes(result)
    assert result["final_answer"]


def test_permanent_failure_goes_to_dead_letter_when_attempts_exhausted() -> None:
    scenario = Scenario(
        id="permanent",
        query="Permanent failure cannot recover after database corruption",
        expected_route=Route.ERROR,
        should_retry=True,
        max_attempts=1,
        tags=["dead_letter", "retry", "permanent_failure"],
    )

    result = run_scenario(scenario, "permanent")

    assert result["attempt"] == 1
    assert "dead_letter" in event_nodes(result)
    assert result["final_answer"]


def test_retry_counter_never_exceeds_max_attempts() -> None:
    scenario = Scenario(
        id="bounded",
        query="Repeated timeout failure persists after all retries",
        expected_route=Route.ERROR,
        should_retry=True,
        max_attempts=2,
        tags=["dead_letter", "retry", "timeout"],
    )

    result = run_scenario(scenario, "bounded")

    assert result["attempt"] <= scenario.max_attempts
    assert event_nodes(result).count("retry") == scenario.max_attempts
