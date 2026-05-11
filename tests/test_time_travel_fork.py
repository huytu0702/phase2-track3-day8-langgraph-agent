from pathlib import Path

from langgraph_agent_lab.runner import (
    fork_from_checkpoint,
    list_thread_history,
    resume_thread,
    run_scenario,
)
from langgraph_agent_lab.state import Route, Scenario


def risky_scenario() -> Scenario:
    return Scenario(
        id="time-travel",
        query="Refund order 12345 and send confirmation email",
        expected_route=Route.RISKY,
        requires_approval=True,
        tags=["risky", "hitl", "checkpoint", "time_travel"],
    )


def approval_checkpoint_id(history: list[dict]) -> str:
    for item in history:
        if "approval" in item["next_nodes"]:
            return str(item["checkpoint_id"])
    raise AssertionError("No approval checkpoint found")


def event_nodes(state: dict) -> list[str]:
    return [event["node"] for event in state.get("events", [])]


def test_fork_from_prior_checkpoint_creates_new_thread_with_divergent_outcome(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("LANGGRAPH_INTERRUPT", "true")
    db_path = tmp_path / "checkpoints.sqlite"
    source_thread_id = "time-source"
    fork_thread_id = "time-fork"

    run_scenario(
        risky_scenario(),
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
    original = resume_thread(
        thread_id=source_thread_id,
        approval={"approved": True, "reviewer": "tester", "comment": "original approve"},
        checkpointer_kind="sqlite",
        database_url=str(db_path),
    )
    forked = fork_from_checkpoint(
        source_thread_id=source_thread_id,
        checkpoint_id=checkpoint_id,
        new_thread_id=fork_thread_id,
        approval={"approved": False, "reviewer": "tester", "comment": "fork reject"},
        checkpointer_kind="sqlite",
        database_url=str(db_path),
    )

    assert original["approval"]["approved"] is True
    assert forked["state"]["thread_id"] == fork_thread_id
    assert forked["state"]["approval"]["approved"] is False
    assert "tool" in event_nodes(original)
    assert "clarify" in event_nodes(forked["state"])


def test_fork_preserves_original_thread_history_immutable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LANGGRAPH_INTERRUPT", "true")
    db_path = tmp_path / "checkpoints.sqlite"
    source_thread_id = "immutable-source"

    run_scenario(
        risky_scenario(),
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
    source_before = list_thread_history(
        thread_id=source_thread_id,
        checkpointer_kind="sqlite",
        database_url=str(db_path),
    )

    fork_from_checkpoint(
        source_thread_id=source_thread_id,
        checkpoint_id=checkpoint_id,
        new_thread_id="immutable-fork",
        approval={"approved": False, "reviewer": "tester", "comment": "fork reject"},
        checkpointer_kind="sqlite",
        database_url=str(db_path),
    )
    source_after = list_thread_history(
        thread_id=source_thread_id,
        checkpointer_kind="sqlite",
        database_url=str(db_path),
    )

    assert [item["checkpoint_id"] for item in source_after] == [
        item["checkpoint_id"] for item in source_before
    ]


def test_fork_from_invalid_checkpoint_id_returns_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LANGGRAPH_INTERRUPT", "true")
    db_path = tmp_path / "checkpoints.sqlite"

    run_scenario(
        risky_scenario(),
        checkpointer_kind="sqlite",
        database_url=str(db_path),
        thread_id="invalid-source",
    )

    try:
        fork_from_checkpoint(
            source_thread_id="invalid-source",
            checkpoint_id="does-not-exist",
            new_thread_id="invalid-fork",
            approval={"approved": False},
            checkpointer_kind="sqlite",
            database_url=str(db_path),
        )
    except ValueError as exc:
        assert "Unknown checkpoint id" in str(exc)
    else:
        raise AssertionError("Expected invalid checkpoint fork to fail")
