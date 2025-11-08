from __future__ import annotations

import re
from typing import Dict, Iterable, List, Set
from urllib.parse import urlparse

from parallax.core.schemas import ExecutionPlan, PlanStep, UIState

INTERACTIVE_ACTIONS = {
    "type",
    "fill",
    "submit",
    "select",
    "upload",
    "check",
    "uncheck",
    "press_key",
    "key_press",
}


class CompletionValidationError(Exception):
    """Raised when a workflow did not reach the expected destinations."""

    def __init__(self, missing: List[str], actual: Iterable[str]):
        self.missing = missing
        self.actual = list(actual)
        message = (
            "Workflow did not reach expected destinations. "
            f"Missing: {', '.join(missing)}"
        )
        super().__init__(message)


def validate_completion(
    plan: ExecutionPlan,
    states: Iterable[UIState],
    min_targets: int = 1,
) -> None:
    """Validate that key navigation targets from the plan were reached."""
    states = list(states)
    mode = _classify_plan(plan)
    expected = _expected_slugs(plan)
    actual = _actual_slugs(states)

    if mode == "explore":
        if len(expected) <= 0:
            return
        required_hits = min(len(expected), max(1, min_targets))
        hits = [slug for slug in expected if slug in actual]
        if len(hits) >= required_hits:
            return
        missing = []
        for slug, label in expected.items():
            if slug not in actual:
                missing.append(label)
            if len(missing) >= required_hits:
                break
        raise CompletionValidationError(missing, actual)
        return

    if mode == "interactive":
        if not _has_interactive_signal(states):
            raise CompletionValidationError(["post-action signal"], actual)


def _classify_plan(plan: ExecutionPlan) -> str:
    interactive_steps = 0
    for step in plan.steps:
        if step.action in INTERACTIVE_ACTIONS:
            interactive_steps += 1
    return "interactive" if interactive_steps else "explore"


def _expected_slugs(plan: ExecutionPlan) -> Dict[str, str]:
    expected: Dict[str, str] = {}
    for step in plan.steps:
        if step.target:
            slug = _first_path_slug(step.target)
            if slug:
                expected.setdefault(slug, step.target)
        if _is_nav_click(step):
            slug = _slugify_text(step.name)
            if slug:
                expected.setdefault(slug, step.name)
    return expected


def _actual_slugs(states: Iterable[UIState]) -> Set[str]:
    slugs: Set[str] = set()
    for state in states:
        slug = _first_path_slug(getattr(state, "url", ""))
        if slug:
            slugs.add(slug)
    return slugs


def _has_interactive_signal(states: Iterable[UIState]) -> bool:
    for state in states:
        action_desc = (state.action or "").lower()
        if any(token in action_desc for token in ("submit", "type", "fill", "upload", "check", "form", "save")):
            meta = state.metadata or {}
            if meta.get("has_toast") or meta.get("form_validity") is True:
                return True
            if meta.get("significance") == "critical" and "form" in (meta.get("significance_reasoning") or "").lower():
                return True
    return False


def _is_nav_click(step: PlanStep) -> bool:
    if step.action != "click" or not step.name:
        return False
    if step.role not in {"link", "button", None}:
        return False
    # Ignore very long labels (likely not navigation)
    if len(step.name) > 40:
        return False
    words = re.findall(r"[A-Za-z]+", step.name)
    return 0 < len(words) <= 3


def _first_path_slug(url: str) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    path = (parsed.path or "").strip("/")
    if not path:
        return None
    segment = path.split("/")[0]
    return _slugify_text(segment)


def _slugify_text(text: str | None) -> str | None:
    if not text:
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(slug) < 3:
        return None
    # Limit to first segment if slug contains multiple sections
    slug = slug.split("-")[0] if slug.count("-") >= 3 else slug
    return slug or None
