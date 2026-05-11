"""Node implementations for the LangGraph workflow."""

from __future__ import annotations

import os

from .state import AgentState, ApprovalDecision, Route, make_event
from .tools import execute_lab_tool

RISKY_KEYWORDS = ("refund", "delete", "send", "cancel", "revoke", "remove", "closure")
TOOL_KEYWORDS = (
    "status",
    "order",
    "lookup",
    "track",
    "shipment",
    "invoice",
    "subscription",
    "search",
    "ticket",
    "customer",
)
ERROR_KEYWORDS = (
    "timeout",
    "failure",
    "unavailable",
    "rate limit",
    "crashed",
    "crash",
    "corruption",
)
MISSING_INFO_PHRASES = ("fix it", "this", "that", "it is", "help me with")
NEGATED_RISK_PHRASES = ("do not want to delete", "don't delete", "do not delete")


def intake_node(state: AgentState) -> dict:
    query = state.get("query", "").strip()
    return {
        "query": query,
        "messages": [f"intake:{query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized")],
    }


def classify_node(state: AgentState) -> dict:
    query = state.get("query", "").lower()
    route = Route.SIMPLE
    risk_level = "low"

    has_negated_risk = any(phrase in query for phrase in NEGATED_RISK_PHRASES)
    has_risky_keyword = any(keyword in query for keyword in RISKY_KEYWORDS)
    has_tool_keyword = any(keyword in query for keyword in TOOL_KEYWORDS)
    has_error_keyword = any(keyword in query for keyword in ERROR_KEYWORDS)
    has_identifier = any(char.isdigit() for char in query) or "#" in query or "inv-" in query
    is_short_missing = len(query.split()) < 5 and any(
        phrase in query for phrase in MISSING_INFO_PHRASES
    )

    if has_risky_keyword and not has_negated_risk:
        route = Route.RISKY
        risk_level = "high"
    elif state.get("should_retry"):
        route = Route.ERROR
    elif is_short_missing or (has_tool_keyword and not has_identifier and "my order" in query):
        route = Route.MISSING_INFO
    elif has_tool_keyword and (has_identifier or not is_short_missing):
        route = Route.TOOL
    elif has_error_keyword:
        route = Route.ERROR

    return {
        "route": route.value,
        "risk_level": risk_level,
        "events": [make_event("classify", "completed", f"route={route.value}")],
    }


def ask_clarification_node(state: AgentState) -> dict:
    question = "Can you provide the order id or the missing context?"
    return {
        "pending_question": question,
        "final_answer": question,
        "events": [make_event("clarify", "completed", "missing information requested")],
    }


def tool_node(state: AgentState) -> dict:
    attempt = int(state.get("attempt", 0))
    result = execute_lab_tool(state)
    return {
        "tool_results": [result],
        "events": [make_event("tool", "completed", f"tool executed attempt={attempt}")],
    }


def risky_action_node(state: AgentState) -> dict:
    return {
        "proposed_action": "prepare external side-effect action; approval required",
        "events": [make_event("risky_action", "pending_approval", "approval required")],
    }


def approval_node(state: AgentState) -> dict:
    if os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true":
        from langgraph.types import interrupt

        value = interrupt(
            {
                "proposed_action": state.get("proposed_action"),
                "risk_level": state.get("risk_level"),
                "scenario_id": state.get("scenario_id"),
            }
        )
        decision = (
            ApprovalDecision(**value)
            if isinstance(value, dict)
            else ApprovalDecision(approved=bool(value))
        )
    else:
        decision = ApprovalDecision(
            approved=True, reviewer="local-cli", comment="non-interrupt mode"
        )

    return {
        "approval": decision.model_dump(),
        "events": [make_event("approval", "completed", f"approved={decision.approved}")],
    }


def retry_or_fallback_node(state: AgentState) -> dict:
    attempt = int(state.get("attempt", 0)) + 1
    return {
        "attempt": attempt,
        "errors": [f"controlled failure attempt={attempt}"],
        "events": [make_event("retry", "completed", "retry attempt recorded", attempt=attempt)],
    }


def answer_node(state: AgentState) -> dict:
    if state.get("tool_results"):
        answer = f"I found: {state['tool_results'][-1]}"
    elif state.get("route") == Route.SIMPLE.value:
        answer = "Here is the requested support guidance."
    else:
        answer = "The request has been handled safely."
    return {
        "final_answer": answer,
        "events": [make_event("answer", "completed", "answer generated")],
    }


def evaluate_node(state: AgentState) -> dict:
    tool_results = state.get("tool_results", [])
    latest = tool_results[-1] if tool_results else ""
    if "ERROR" in latest:
        return {
            "evaluation_result": "needs_retry",
            "events": [
                make_event("evaluate", "completed", "tool result indicates failure, retry needed")
            ],
        }
    return {
        "evaluation_result": "success",
        "events": [make_event("evaluate", "completed", "tool result satisfactory")],
    }


def dead_letter_node(state: AgentState) -> dict:
    return {
        "final_answer": (
            "Request could not be completed after maximum retry attempts. "
            "Logged for manual review."
        ),
        "events": [
            make_event(
                "dead_letter",
                "completed",
                f"max retries exceeded, attempt={state.get('attempt', 0)}",
            )
        ],
    }


def finalize_node(state: AgentState) -> dict:
    return {"events": [make_event("finalize", "completed", "workflow finished")]}
