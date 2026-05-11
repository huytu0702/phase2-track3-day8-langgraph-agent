from pathlib import Path

from langgraph_agent_lab.runner import list_thread_history, run_scenario
from langgraph_agent_lab.state import Route, Scenario


def test_history_listing_returns_checkpoints_for_existing_thread_id(tmp_path: Path) -> None:
    db_path = tmp_path / "checkpoints.sqlite"
    thread_id = "history-existing"
    scenario = Scenario(id="history", query="How do I reset MFA?", expected_route=Route.SIMPLE)

    run_scenario(
        scenario,
        checkpointer_kind="sqlite",
        database_url=str(db_path),
        thread_id=thread_id,
    )
    history = list_thread_history(
        thread_id=thread_id,
        checkpointer_kind="sqlite",
        database_url=str(db_path),
    )

    assert history
    assert all(item["thread_id"] == thread_id for item in history)
    assert any(item["last_node"] == "finalize" for item in history)
    assert all(item["checkpoint_id"] for item in history)


def test_history_listing_returns_empty_for_unknown_thread_id(tmp_path: Path) -> None:
    db_path = tmp_path / "checkpoints.sqlite"

    history = list_thread_history(
        thread_id="missing-thread",
        checkpointer_kind="sqlite",
        database_url=str(db_path),
    )

    assert history == []


def test_history_listing_is_scoped_to_single_thread_id(tmp_path: Path) -> None:
    db_path = tmp_path / "checkpoints.sqlite"
    first = Scenario(id="first", query="How do I reset MFA?", expected_route=Route.SIMPLE)
    second = Scenario(id="second", query="Check order 12345", expected_route=Route.TOOL)

    run_scenario(
        first,
        checkpointer_kind="sqlite",
        database_url=str(db_path),
        thread_id="thread-a",
    )
    run_scenario(
        second,
        checkpointer_kind="sqlite",
        database_url=str(db_path),
        thread_id="thread-b",
    )
    history = list_thread_history(
        thread_id="thread-a",
        checkpointer_kind="sqlite",
        database_url=str(db_path),
    )

    assert history
    assert {item["thread_id"] for item in history} == {"thread-a"}
    assert all(item["scenario_id"] == "first" for item in history if item["scenario_id"])
