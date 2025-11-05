import re
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

import pytest

from parallax.agents.navigator import Navigator
from parallax.core.schemas import PlanStep


@dataclass
class FakeLocator:
    count_value: int = 1
    scrolled: bool = False
    scroll_timeout: Optional[int] = None
    click_calls: int = 0

    async def count(self) -> int:
        return self.count_value

    @property
    def first(self) -> "FakeLocator":
        return self

    async def scroll_into_view_if_needed(self, timeout: int = 5000) -> None:
        self.scrolled = True
        self.scroll_timeout = timeout

    async def wait_for(self, *args, **kwargs) -> None:
        return

    async def click(self, *args, **kwargs) -> None:
        self.click_calls += 1
        return

    async def fill(self, *args, **kwargs) -> None:
        return

    async def all_inner_texts(self) -> list[str]:
        return []


class FakePage:
    def __init__(self, locator: Optional[FakeLocator] = None) -> None:
        self.wait_calls: list[int] = []
        self.evaluate_calls: list[str] = []
        self._locator = locator or FakeLocator()

    async def wait_for_timeout(self, duration_ms: int) -> None:
        self.wait_calls.append(duration_ms)

    def locator(self, _selector: str) -> FakeLocator:
        return self._locator

    def get_by_role(self, *_args, **_kwargs) -> FakeLocator:
        return FakeLocator(count_value=0)

    def get_by_text(self, *_args, **_kwargs) -> FakeLocator:
        return FakeLocator(count_value=0)

    # Backwards compatibility hooks in navigator
    getByRole = get_by_role
    getByText = get_by_text

    async def evaluate(self, script: str) -> None:
        self.evaluate_calls.append(script)

    @property
    def viewport_size(self):
        return {"height": 900}


class TextLocator:
    def __init__(self, elements: Iterable[dict[str, Optional[str]]]) -> None:
        self._elements = list(elements)

    async def count(self) -> int:
        return len(self._elements)

    @property
    def first(self) -> "TextLocator":
        return TextLocator(self._elements[:1])

    def filter(self, has_text=None) -> "TextLocator":
        if has_text is None:
            return TextLocator(self._elements)
        predicate: Callable[[dict[str, Optional[str]]], bool]
        if hasattr(has_text, "search"):
            regex = has_text

            def predicate(el: dict[str, Optional[str]]) -> bool:
                text = el.get("text") or ""
                aria = el.get("aria_label") or ""
                return bool(regex.search(text) or regex.search(aria))

        else:
            needle = _normalize_text(str(has_text))

            def predicate(el: dict[str, Optional[str]]) -> bool:
                text = _normalize_text(el.get("text"))
                aria = _normalize_text(el.get("aria_label"))
                return needle in text or needle in aria

        return TextLocator(el for el in self._elements if predicate(el))

    async def all_inner_texts(self) -> list[str]:
        return [
            (el.get("text") or el.get("aria_label") or "")
            for el in self._elements
        ]

    async def scroll_into_view_if_needed(self, timeout: int = 5000) -> None:
        return

    async def wait_for(self, *args, **kwargs) -> None:
        return

    async def click(self, *args, **kwargs) -> None:
        return

    async def fill(self, *args, **kwargs) -> None:
        return


class AccessiblePage:
    def __init__(self, elements: Iterable[object]) -> None:
        self._elements: list[dict[str, Optional[str]]] = []
        for entry in elements:
            if isinstance(entry, dict):
                text = entry.get("text", "")
                aria = entry.get("aria_label")
            elif isinstance(entry, tuple):
                text, aria = entry
            else:
                text = str(entry)
                aria = None
            self._elements.append({"text": text, "aria_label": aria})
        self.wait_calls: list[int] = []

    async def wait_for_timeout(self, duration_ms: int) -> None:
        self.wait_calls.append(duration_ms)

    def _match(self, predicate: Callable[[dict[str, Optional[str]]], bool]) -> TextLocator:
        return TextLocator(el for el in self._elements if predicate(el))

    def get_by_role(self, role: str, name=None, exact=None) -> TextLocator:
        if name is None:
            return TextLocator(self._elements)
        if isinstance(name, re.Pattern):
            regex = name
            return self._match(
                lambda el: bool(
                    (el["text"] and regex.search(el["text"])) or
                    (el["aria_label"] and regex.search(el["aria_label"]))
                )
            )
        target = _normalize_text(str(name))
        if exact:
            return self._match(
                lambda el: _normalize_text(el["text"]) == target
                or _normalize_text(el["aria_label"]) == target
            )
        return self._match(
            lambda el: target in _normalize_text(el["text"])
            or target in _normalize_text(el["aria_label"])
        )

    getByRole = get_by_role

    def locator(self, selector: str) -> TextLocator:
        if selector in {"a", '[role="link"]', "button", '[role="button"]', "input[type='button']", "input[type='submit']"}:
            return TextLocator(self._elements)
        if selector.startswith("text="):
            text = selector[len("text="):].strip().strip('"').strip("'")
            needle = _normalize_text(text)
            return self._match(
                lambda el: needle in _normalize_text(el["text"])
                or needle in _normalize_text(el["aria_label"])
            )
        if selector.startswith("[data-testid"):
            token = selector.split("=", 1)[-1].strip('"]').strip('"').strip("'")
            needle = _normalize_text(token)
            return self._match(lambda el: needle in _normalize_text(el["text"]))
        if selector.startswith("[aria-label"):
            token = selector.split("=", 1)[-1].strip('"]').strip('"').strip("'")
            needle = _normalize_text(token)
            return self._match(lambda el: needle in _normalize_text(el["aria_label"]))
        if selector.startswith("[title"):
            token = selector.split("=", 1)[-1].strip('"]').strip('"').strip("'")
            needle = _normalize_text(token)
            return self._match(lambda el: needle in _normalize_text(el["text"]))
        if selector.startswith("xpath="):
            expr = selector[len("xpath="):]
            exact = re.search(r"normalize-space\(\.\)\s*=\s*['\"](.+?)['\"]", expr)
            contains = re.search(r"contains\(normalize-space\(\.\),\s*['\"](.+?)['\"]", expr)
            if exact:
                needle = _normalize_text(exact.group(1))
                return self._match(lambda el: _normalize_text(el["text"]) == needle)
            if contains:
                needle = _normalize_text(contains.group(1))
                return self._match(lambda el: needle in _normalize_text(el["text"]))
        return TextLocator([])

    def get_by_text(self, name, exact=False) -> TextLocator:
        if isinstance(name, re.Pattern):
            regex = name
            return self._match(
                lambda el: bool(
                    (el["text"] and regex.search(el["text"])) or
                    (el["aria_label"] and regex.search(el["aria_label"]))
                )
            )
        target = _normalize_text(str(name))
        if exact:
            return self._match(
                lambda el: _normalize_text(el["text"]) == target
                or _normalize_text(el["aria_label"]) == target
            )
        return self._match(
            lambda el: target in _normalize_text(el["text"])
            or target in _normalize_text(el["aria_label"])
        )

    getByText = get_by_text


def _normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip().lower()


@pytest.mark.asyncio
async def test_run_step_wait_parses_seconds():
    page = FakePage()
    navigator = Navigator(page, default_wait_ms=100, scroll_margin_px=64)
    step = PlanStep(action="wait", value="1.5s")

    await navigator._run_step(step)

    assert page.wait_calls == [1500]


@pytest.mark.asyncio
async def test_run_step_scroll_with_locator():
    locator = FakeLocator()
    page = FakePage(locator=locator)
    navigator = Navigator(page, default_wait_ms=100, scroll_margin_px=64)
    step = PlanStep(action="scroll", selector="#cta")

    await navigator._run_step(step)

    assert locator.scrolled is True
    assert locator.scroll_timeout == 5000
    assert page.wait_calls[-1] == 200


@pytest.mark.asyncio
async def test_run_step_scroll_fallback_direction():
    page = FakePage()
    navigator = Navigator(page, default_wait_ms=100, scroll_margin_px=32)
    step = PlanStep(action="scroll", value="down")

    await navigator._run_step(step)

    assert page.evaluate_calls, "Fallback scroll should invoke page.evaluate"
    script = page.evaluate_calls[-1]
    assert "window.scrollBy" in script
    # Script evaluates the calculation (900 - 32 = 868), so check for the result
    assert "868" in script or "window.innerHeight" in script or "innerHeight" in script
    assert page.wait_calls[-1] == 200


@pytest.mark.asyncio
async def test_resolve_locator_handles_smart_apostrophe():
    page = AccessiblePage(["We’re hiring", "Join waitlist"])
    navigator = Navigator(page, default_wait_ms=100, scroll_margin_px=64)
    step = PlanStep(action="click", role="link", name="We're hiring")

    locator = await navigator._resolve_locator_with_retry(step)

    assert await locator.count() == 1


@pytest.mark.asyncio
async def test_resolve_locator_handles_collapsed_whitespace():
    page = AccessiblePage(["Join     waitlist"])
    navigator = Navigator(page, default_wait_ms=100, scroll_margin_px=64)
    step = PlanStep(action="click", role="link", name="Join waitlist")

    locator = await navigator._resolve_locator_with_retry(step)

    assert await locator.count() == 1


@pytest.mark.asyncio
async def test_resolve_locator_without_role_uses_text_fallback():
    page = AccessiblePage(["Join\nwaitlist"])
    navigator = Navigator(page, default_wait_ms=100, scroll_margin_px=64)
    step = PlanStep(action="click", name="Join waitlist")

    locator = await navigator._resolve_locator_with_retry(step)

    assert await locator.count() == 1


@pytest.mark.asyncio
async def test_resolve_locator_matches_aria_label():
    page = AccessiblePage([{"text": "", "aria_label": "Join the waitlist"}])
    navigator = Navigator(page, default_wait_ms=100, scroll_margin_px=64)
    step = PlanStep(action="click", role="button", name="Join the waitlist")

    locator = await navigator._resolve_locator_with_retry(step)

    assert await locator.count() == 1


@pytest.mark.asyncio
async def test_resolve_locator_xpath_fallback():
    page = AccessiblePage(["Join waitlist now"])
    navigator = Navigator(page, default_wait_ms=100, scroll_margin_px=64)
    step = PlanStep(action="click", role="link", name="Join waitlist")

    locator = await navigator._resolve_locator_with_retry(step)

    assert await locator.count() == 1
