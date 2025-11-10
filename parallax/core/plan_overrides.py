from __future__ import annotations

from parallax.core.schemas import ExecutionPlan, PlanStep

GOOGLE_SEARCH_INPUT_SELECTOR = ":is(input,textarea)[name='q']"
GOOGLE_RESULTS_SCOPE = "#search"


def apply_site_overrides(plan: ExecutionPlan, start_url: str | None) -> ExecutionPlan:
    """Mutate plan steps to account for known site quirks."""
    if not start_url:
        return plan
    # Convert HttpUrl to string if needed (from Pydantic validation)
    start_url_str = str(start_url)
    lowered = start_url_str.lower()
    if "google." in lowered:
        _tune_google_plan(plan)
    elif "wikipedia.org" in lowered:
        _tune_wikipedia_plan(plan)
    return plan


def _tune_google_plan(plan: ExecutionPlan) -> None:
    for step in plan.steps:
        if step.action in {"type", "fill"} and not step.selector:
            _ensure_google_search_selector(step)
            continue
        if step.action == "click" and not step.selector and step.name:
            selector = _google_result_selector(step.name)
            if selector:
                step.selector = selector
                step.role = None


def _ensure_google_search_selector(step: PlanStep) -> None:
    step.selector = GOOGLE_SEARCH_INPUT_SELECTOR
    step.role = None


def _google_result_selector(label: str | None) -> str | None:
    if not label:
        return None
    text = label.strip()
    if not text:
        return None
    if _looks_like_domain(text):
        fragment = _domain_fragment(text)
        if fragment:
            escaped = _escape_attr_value(fragment)
            return f'{GOOGLE_RESULTS_SCOPE} a[href*="{escaped}"]'
    escaped_text = _escape_selector_text(text)
    return f'{GOOGLE_RESULTS_SCOPE} a:has-text("{escaped_text}")'


def _looks_like_domain(text: str) -> bool:
    return "." in text and " " not in text


def _domain_fragment(text: str) -> str:
    fragment = text.lower()
    for prefix in ("https://", "http://"):
        if fragment.startswith(prefix):
            fragment = fragment[len(prefix):]
    fragment = fragment.strip("/ ")
    return fragment.split("/")[0] if fragment else ""


def _escape_selector_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _escape_attr_value(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


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
