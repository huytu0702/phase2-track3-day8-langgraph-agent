from __future__ import annotations

from .state import AgentState


def should_inject_tool_failure(state: AgentState) -> bool:
    if not state.get("should_retry"):
        return False

    attempt = int(state.get("attempt", 0))
    tags = set(state.get("tags", []))
    if "dead_letter" in tags or "permanent_failure" in tags:
        return True

    return attempt < 2


def fault_message(state: AgentState) -> str:
    tags = ",".join(state.get("tags", [])) or "retry"
    return f"ERROR: controlled fault attempt={state.get('attempt', 0)} tags={tags}"
