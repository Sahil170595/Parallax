import pytest

from parallax.core.completion import CompletionValidationError, validate_completion
from parallax.core.schemas import ExecutionPlan, PlanStep, UIState


def _state(url: str) -> UIState:
    return UIState(
        id="state",
        url=url,
        description="",
        has_modal=False,
        action=None,
        screenshots={},
        metadata={},
        state_signature=url,
    )


def test_validate_completion_missing_targets():
    plan = ExecutionPlan(
        steps=[
            PlanStep(action="click", role="link", name="Pricing"),
            PlanStep(action="click", role="link", name="Product"),
        ]
    )
    states = [_state("https://linear.app/pricing")]
    with pytest.raises(CompletionValidationError):
        validate_completion(plan, states, min_targets=2)


def test_validate_completion_passes_with_all_targets():
    plan = ExecutionPlan(
        steps=[
            PlanStep(action="click", role="link", name="Pricing"),
            PlanStep(action="click", role="link", name="Product"),
        ]
    )
    states = [
        _state("https://linear.app/pricing"),
        _state("https://linear.app/product"),
    ]
    validate_completion(plan, states, min_targets=2)


def test_validate_completion_respects_min_targets():
    plan = ExecutionPlan(
        steps=[
            PlanStep(action="click", role="link", name="Pricing"),
            PlanStep(action="click", role="link", name="Security"),
            PlanStep(action="click", role="link", name="Customers"),
        ]
    )
    states = [
        _state("https://linear.app/pricing"),
        _state("https://linear.app/security"),
    ]
    # Require only 2 hits even though plan has 3 targets
    validate_completion(plan, states, min_targets=2)


def test_validate_completion_interactive_requires_signal():
    plan = ExecutionPlan(
        steps=[
            PlanStep(action="type", selector="input[name='title']", value="Foo"),
            PlanStep(action="submit", selector="button[type='submit']"),
        ]
    )
    states = [
        _state("https://example.com/form"),
    ]
    with pytest.raises(CompletionValidationError):
        validate_completion(plan, states)

    success_state = _state("https://example.com/form")
    success_state.action = "submit(button[type='submit'])"
    success_state.metadata = {"has_toast": True}
    validate_completion(plan, [success_state])
