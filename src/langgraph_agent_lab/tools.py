from __future__ import annotations

from .faults import fault_message, should_inject_tool_failure
from .state import AgentState


def execute_lab_tool(state: AgentState) -> str:
    if should_inject_tool_failure(state):
        return fault_message(state)

    query = state.get("query", "")
    route = state.get("route", "unknown")
    if route == "risky":
        approval = state.get("approval") or {}
        return f"approved action recorded for reviewer={approval.get('reviewer', 'unknown')}"
    if any(keyword in query.lower() for keyword in ("order", "tracking", "shipment")):
        return "order_status=processing; evidence=local_order_tool"
    if "invoice" in query.lower():
        return "invoice_status=available; evidence=local_invoice_tool"
    if "subscription" in query.lower():
        return "subscription_status=active; evidence=local_subscription_tool"
    return "tool_result=completed; evidence=local_lab_tool"
