import json
from pathlib import Path

import pytest

from parallax.agents.navigator import Navigator
from parallax.core.constitution import ConstitutionViolation, FailureStore
from parallax.core.schemas import ExecutionPlan, PlanStep


class DummyPage:
    def __init__(self, url: str) -> None:
        self._url = url

    @property
    def url(self) -> str:
        return self._url


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
