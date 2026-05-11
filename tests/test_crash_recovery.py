from pathlib import Path

from langgraph_agent_lab.runner import resume_thread, run_scenario
from langgraph_agent_lab.state import Route, Scenario


def test_interrupted_thread_can_resume_after_graph_rebuild(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LANGGRAPH_INTERRUPT", "true")
    db_path = tmp_path / "checkpoints.sqlite"
    thread_id = "recover-thread"
    scenario = Scenario(
        id="recover",
        query="Refund order 12345 after approval",
        expected_route=Route.RISKY,
        requires_approval=True,
        tags=["risky", "hitl", "checkpoint"],
    )

    interrupted = run_scenario(
        scenario,
        checkpointer_kind="sqlite",
        database_url=str(db_path),
        thread_id=thread_id,
    )
    resumed = resume_thread(
        thread_id=thread_id,
        approval={"approved": True, "reviewer": "tester", "comment": "after restart"},
        checkpointer_kind="sqlite",
        database_url=str(db_path),
    )

    assert interrupted.interrupted is True
    assert resumed["approval"]["approved"] is True
    assert [event["node"] for event in resumed["events"]][-1] == "finalize"


def test_resume_fails_cleanly_for_missing_thread_after_restart(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LANGGRAPH_INTERRUPT", "true")
    db_path = tmp_path / "checkpoints.sqlite"

    try:
        resume_thread(
            thread_id="missing-thread",
            approval={"approved": True, "reviewer": "tester", "comment": "missing"},
            checkpointer_kind="sqlite",
            database_url=str(db_path),
        )
    except ValueError as exc:
        assert "No resumable checkpoint" in str(exc)
    else:
        raise AssertionError("Expected missing thread resume to fail")
