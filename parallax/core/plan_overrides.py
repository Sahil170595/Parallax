from __future__ import annotations

from parallax.core.schemas import ExecutionPlan


def apply_site_overrides(plan: ExecutionPlan, start_url: str | None) -> ExecutionPlan:
    """Mutate plan steps to account for known site quirks."""
    if not start_url:
        return plan
    lowered = start_url.lower()
    if "wikipedia.org" in lowered:
        _tune_wikipedia_plan(plan)
    return plan


def _tune_wikipedia_plan(plan: ExecutionPlan) -> None:
    search_selector = "input[name='search']"
    submit_selector = "button#searchButton"
    for step in plan.steps:
        if step.action in {"type", "fill"}:
            if not step.selector or "search" in (step.selector or ""):
                step.selector = search_selector
        if step.action == "focus" and (not step.selector or "search" in step.selector):
            step.selector = search_selector
        if step.action in {"click", "submit"}:
            name = (step.name or "").lower()
            selector = (step.selector or "").lower()
            if "search" in name or "search" in selector:
                step.selector = submit_selector
                step.name = None
                step.role = None
