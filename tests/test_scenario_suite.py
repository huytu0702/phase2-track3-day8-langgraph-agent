from pathlib import Path

from langgraph_agent_lab.scenarios import load_scenarios
from langgraph_agent_lab.state import Route

SCENARIOS_PATH = Path("data/sample/scenarios.jsonl")


def test_scenarios_jsonl_all_lines_parse_as_scenario() -> None:
    scenarios = load_scenarios(SCENARIOS_PATH)

    assert len(scenarios) >= 37
    assert all(scenario.id and scenario.query for scenario in scenarios)


def test_scenario_ids_are_unique() -> None:
    scenarios = load_scenarios(SCENARIOS_PATH)
    scenario_ids = [scenario.id for scenario in scenarios]

    assert len(scenario_ids) == len(set(scenario_ids))


def test_route_coverage_includes_all_required_categories() -> None:
    scenarios = load_scenarios(SCENARIOS_PATH)
    routes = {scenario.expected_route for scenario in scenarios}

    assert {Route.SIMPLE, Route.TOOL, Route.MISSING_INFO, Route.RISKY, Route.ERROR} <= routes


def test_retry_and_dead_letter_presence() -> None:
    scenarios = load_scenarios(SCENARIOS_PATH)

    assert any(scenario.should_retry for scenario in scenarios)
    assert any("dead_letter" in scenario.tags for scenario in scenarios)


def test_risky_scenarios_require_approval() -> None:
    scenarios = load_scenarios(SCENARIOS_PATH)

    assert all(
        scenario.requires_approval
        for scenario in scenarios
        if scenario.expected_route == Route.RISKY
    )


def test_retry_scenarios_have_positive_max_attempts() -> None:
    scenarios = load_scenarios(SCENARIOS_PATH)

    assert all(scenario.max_attempts >= 1 for scenario in scenarios if scenario.should_retry)
