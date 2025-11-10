from parallax.core.plan_overrides import (
    GOOGLE_SEARCH_INPUT_SELECTOR,
    apply_site_overrides,
)
from parallax.core.schemas import ExecutionPlan, PlanStep


def test_google_override_sets_search_field_selector():
    plan = ExecutionPlan(
        steps=[
            PlanStep(action="type", value="softlight careers", selector=None),
        ]
    )

    apply_site_overrides(plan, "https://www.google.com/search?q=softlight")

    assert plan.steps[0].selector == GOOGLE_SEARCH_INPUT_SELECTOR


def test_google_override_prefers_domain_in_search_results():
    plan = ExecutionPlan(
        steps=[
            PlanStep(action="click", name="softlight.com", selector=None),
        ]
    )

    apply_site_overrides(plan, "https://www.google.com/search?q=softlight")

    assert plan.steps[0].selector == '#search a[href*="softlight.com"]'


def test_google_override_targets_textual_results_when_not_domain():
    plan = ExecutionPlan(
        steps=[
            PlanStep(action="click", name="We're hiring", selector=None),
        ]
    )

    apply_site_overrides(plan, "https://www.google.com/search?q=softlight")

    assert plan.steps[0].selector == '#search a:has-text("We\'re hiring")'


def test_non_google_start_url_is_left_untouched():
    plan = ExecutionPlan(
        steps=[
            PlanStep(action="click", name="We're hiring", selector=None),
        ]
    )

    apply_site_overrides(plan, "https://softlight.com")

    assert plan.steps[0].selector is None
