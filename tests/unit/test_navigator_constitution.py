import json
from pathlib import Path

import pytest

from parallax.agents.navigator import Navigator
from parallax.core.constitution import (
    ConstitutionViolation,
    FailureStore,
    ValidationFailure,
    ValidationLevel,
)
from parallax.core.schemas import ExecutionPlan, PlanStep


class DummyPage:
    def __init__(self, url: str) -> None:
        self._url = url

    @property
    def url(self) -> str:
        return self._url


class AsyncDummyPage(DummyPage):
    async def goto(self, url: str, *_args, **_kwargs) -> None:
        self._url = url

    async def wait_for_load_state(self, *_args, **_kwargs) -> None:  # noqa: D401
        return None


def read_failures(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_navigator_finalize_raises_on_critical_failure(tmp_path):
    page = DummyPage("")
    store_path = tmp_path / "failures"
    navigator = Navigator(page, failure_store=FailureStore(store_path))
    plan = ExecutionPlan(steps=[])

    with pytest.raises(ConstitutionViolation):
        navigator.finalize(plan, {"page": page})

    failures_file = store_path / "constitution_failures.jsonl"
    failures = read_failures(failures_file)
    assert failures, "failure report should be saved for critical issues"
    assert failures[-1]["failures"][0]["rule_name"] == "navigation_success"


def test_navigator_finalize_returns_warnings(tmp_path):
    page = DummyPage("https://example.com")
    store_path = tmp_path / "warn_failures"
    navigator = Navigator(page, failure_store=FailureStore(store_path))
    plan = ExecutionPlan(steps=[PlanStep(action="navigate", target="https://example.com")])

    report = navigator.finalize(
        plan,
        {"page": page, "action_budget": 1, "action_count": 5},
    )

    assert report.passed is True
    assert report.warnings, "warning-level violations should be returned"

    failures_file = store_path / "constitution_failures.jsonl"
    failures = read_failures(failures_file)
    assert failures, "warnings should also be persisted"
    assert failures[-1]["warnings"][0]["rule_name"] == "action_budget"


@pytest.mark.asyncio
async def test_navigator_heal_navigation_success(tmp_path):
    page = AsyncDummyPage("")
    navigator = Navigator(page, failure_store=FailureStore(tmp_path / "heal"))
    plan = ExecutionPlan(steps=[PlanStep(action="navigate", target="https://example.com")])
    failure = ValidationFailure(
        rule_name="navigation_success",
        rule_description="Page must reach target",
        level=ValidationLevel.CRITICAL,
        reason="Page did not load",
        details={},
    )

    recovered, adjustments = await navigator.heal(
        plan,
        {"page": page, "start_url": "https://example.com", "action_budget": 3},
        [failure],
    )

    assert recovered is True
    assert adjustments.get("start_url") == "https://example.com"


@pytest.mark.asyncio
async def test_navigator_heal_adjusts_action_budget(tmp_path):
    page = AsyncDummyPage("https://example.com")
    navigator = Navigator(page, failure_store=FailureStore(tmp_path / "budget"))
    plan = ExecutionPlan(steps=[PlanStep(action="navigate", target="https://example.com")])
    failure = ValidationFailure(
        rule_name="action_budget",
        rule_description="Budget exceeded",
        level=ValidationLevel.WARNING,
        reason="Exceeded budget",
        details={},
    )

    recovered, adjustments = await navigator.heal(
        plan,
        {"page": page, "start_url": "https://example.com", "action_budget": 2},
        [failure],
    )

    assert recovered is True
    assert adjustments.get("action_budget") == 7
    history = adjustments.get("plan_context", {}).get("failure_history", [])
    assert history and history[-1]["rule"] == "action_budget"
