from __future__ import annotations

import inspect
import re
import unicodedata
from time import perf_counter
from typing import Any, Dict, Iterable, List, Optional, Tuple

from parallax.agents.navigator import Navigator
from parallax.core.logging import get_logger


log = get_logger("navigator_pro")


class NavigatorPro(Navigator):
    """
    Experimental navigator with more resilient locator resolution.

    The public API matches :class:`Navigator`; you can swap this class in
    wherever the standard navigator is used to compare behaviours.
    """

    _SMART_TO_ASCII_TABLE = str.maketrans({
        "’": "'",
        "‘": "'",
        "‛": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "–": "-",
        "—": "-",
        "‑": "-",
        "\u00a0": " ",
    })

    _ASCII_TO_SMART_TABLE = str.maketrans({
        "'": "’",
        '"': "”",
    })

    async def _resolve_locator_with_retry(self, step, attempt: int = 0):
        """
        Strengthen the base locator cascade with additional fallbacks and logging.
        """
        variants = self._text_variants(step.name) if step.name else []
        start_time = perf_counter()

        if step.role:
            locator, attempts = await self._first_matching_locator(
                self._role_locators(step.role, variants),
                strategy="role",
            )
            if locator:
                self._record_locator_result(step, "role", attempts, True, start_time)
                return locator
            self._record_locator_result(step, "role", attempts, False, start_time)

        if variants:
            locator = await self._resolve_data_testid(variants)
            if locator:
                self._record_locator_result(step, "data-testid", 1, True, start_time)
                return locator
            self._record_locator_result(step, "data-testid", 1, False, start_time)

        if step.selector:
            locator, attempts = await self._first_matching_locator(
                (self.page.locator(step.selector),),
                strategy="selector",
            )
            if locator:
                self._record_locator_result(step, "selector", attempts, True, start_time)
                return locator
            self._record_locator_result(step, "selector", attempts, False, start_time)

        if variants:
            locator, attempts = await self._first_matching_locator(
                self._text_locators(variants, preferred_role=step.role),
                strategy="text",
            )
            if locator:
                self._record_locator_result(step, "text", attempts, True, start_time)
                return locator
            self._record_locator_result(step, "text", attempts, False, start_time)

            locator, attempts = await self._first_matching_locator(
                self._xpath_locators(variants, preferred_role=step.role),
                strategy="xpath",
            )
            if locator:
                self._record_locator_result(step, "xpath", attempts, True, start_time)
                return locator
            self._record_locator_result(step, "xpath", attempts, False, start_time)

        await self._log_locator_diagnostics(step, variants)
        raise ValueError(f"Insufficient selector info for {step.action}")

    # ------------------------------------------------------------------ #
    # Helper utilities
    # ------------------------------------------------------------------ #

    def _page_method(self, *names: str):
        for name in names:
            method = getattr(self.page, name, None)
            if callable(method):
                return method
        raise AttributeError(f"Page object missing required methods {names}")

    def _page_get_by_role(self, *args, **kwargs):
        return self._page_method("get_by_role", "getByRole")(*args, **kwargs)

    def _page_get_by_text(self, *args, **kwargs):
        return self._page_method("get_by_text", "getByText")(*args, **kwargs)

    async def _first_matching_locator(
        self,
        locators: Iterable[Any],
        strategy: str,
    ) -> Tuple[Optional[Any], int]:
        attempts = 0
        for locator in locators:
            if locator is None:
                continue
            attempts += 1
            try:
                count = await locator.count()
            except Exception as exc:
                log.debug("navigator_pro_locator_count_failed", strategy=strategy, error=str(exc))
                continue
            if count <= 0:
                continue
            candidate = locator
            try:
                if hasattr(locator, "first"):
                    candidate = locator.first if count > 1 else locator
            except Exception as exc:
                log.debug("navigator_pro_locator_first_failed", strategy=strategy, error=str(exc))
                candidate = locator
            if await self._ensure_visible(candidate, strategy):
                return candidate, attempts
        return None, attempts

    async def _ensure_visible(self, locator: Any, strategy: str) -> bool:
        """
        Guard against hidden elements before returning a candidate locator.
        """
        try:
            wait_for = getattr(locator, "wait_for", None)
            if callable(wait_for):
                await wait_for(state="visible", timeout=2000)
                return True
            is_visible = getattr(locator, "is_visible", None)
            if callable(is_visible):
                result = is_visible()
                if inspect.isawaitable(result):
                    result = await result
                return bool(result)
        except Exception as exc:
            log.debug("navigator_pro_locator_visibility_failed", strategy=strategy, error=str(exc))
            return False
        return True

    def _text_variants(self, text: str) -> List[str]:
        variants: List[str] = []
        seen = set()

        def add(value: str):
            collapsed = self._collapse_whitespace(value)
            if collapsed and collapsed not in seen:
                seen.add(collapsed)
                variants.append(collapsed)

        base = str(text)
        normalized = unicodedata.normalize("NFKC", base)
        add(base)
        add(normalized)
        add(base.translate(self._SMART_TO_ASCII_TABLE))
        add(normalized.translate(self._SMART_TO_ASCII_TABLE))
        add(base.translate(self._ASCII_TO_SMART_TABLE))
        add(normalized.translate(self._ASCII_TO_SMART_TABLE))
        add(base.lower())
        add(base.casefold())
        add(base.title())
        return variants

    def _collapse_whitespace(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    def _role_locators(self, role: str, variants: List[str]):
        regex_cache: Dict[str, re.Pattern[str]] = {}
        for variant in variants:
            yield self._page_get_by_role(role, name=variant, exact=True)
            yield self._page_get_by_role(role, name=variant, exact=False)
            regex = regex_cache.setdefault(variant, self._text_regex(variant))
            yield self._page_get_by_role(role, name=regex)
            try:
                yield self._page_get_by_role(role).filter(has_text=regex)
            except Exception:
                pass
            for selector in self._role_selector_candidates(role):
                try:
                    yield self.page.locator(selector).filter(has_text=regex)
                except Exception:
                    continue

    def _text_locators(self, variants: List[str], preferred_role: Optional[str]):
        for variant in variants:
            regex = self._text_regex(variant)
            literal = self._selector_literal(variant)
            locators = [
                self._page_get_by_text(variant, exact=True),
                self._page_get_by_text(variant, exact=False),
                self._page_get_by_text(regex),
                self.page.locator(f"text={self._selector_literal(variant)}"),
                self.page.locator(f"[aria-label={literal}]"),
                self.page.locator(f"[aria-label*={literal}]"),
                self.page.locator(f"[title={literal}]"),
                self.page.locator(f"[title*={literal}]"),
            ]
            for selector in self._role_selector_candidates(preferred_role):
                try:
                    locators.append(self.page.locator(selector).filter(has_text=regex))
                except Exception:
                    continue
            try:
                locators.append(self.page.locator("a").filter(has_text=regex))
            except Exception:
                pass
            try:
                locators.append(self.page.locator('[role="link"]').filter(has_text=regex))
            except Exception:
                pass
            for locator in locators:
                yield locator

    def _xpath_locators(self, variants: List[str], preferred_role: Optional[str]):
        conditions = self._role_xpath_conditions(preferred_role)
        predicate = " or ".join(conditions) if conditions else None
        for variant in variants:
            literal = self._xpath_literal(variant)
            if predicate:
                yield self.page.locator(f"xpath=//*[{predicate}][normalize-space(.)={literal}]")
                yield self.page.locator(f"xpath=//*[{predicate}][contains(normalize-space(.), {literal})]")
            else:
                yield self.page.locator(f"xpath=//*[normalize-space(.)={literal}]")
                yield self.page.locator(f"xpath=//*[contains(normalize-space(.), {literal})]")

    def _role_selector_candidates(self, role: Optional[str]) -> List[str]:
        if not role:
            return []
        mapping = {
            "link": ["a", '[role="link"]'],
            "button": ["button", '[role="button"]', "input[type='button']", "input[type='submit']"],
            "menuitem": ['[role="menuitem"]'],
            "tab": ['[role="tab"]'],
            "checkbox": ["input[type='checkbox']", '[role="checkbox"]"],
            "radio": ["input[type='radio']", '[role="radio"]'],
            "option": ["option", '[role="option"]"],
        }
        return mapping.get(role, [f'[role="{role}"]'])

    def _role_xpath_conditions(self, role: Optional[str]) -> List[str]:
        base = ["self::a", "@role='link'", "@role='button'", "self::button", "self::input[@type='button']", "self::input[@type='submit']"]
        mapping = {
            "link": ["self::a", "@role='link'"],
            "button": ["self::button", "@role='button'", "self::input[@type='button']", "self::input[@type='submit']"],
            "menuitem": ["@role='menuitem'"],
            "tab": ["@role='tab'"],
            "checkbox": ["@role='checkbox'", "self::input[@type='checkbox']"],
            "radio": ["@role='radio'", "self::input[@type='radio']"],
            "option": ["@role='option'", "self::option"],
        }
        return mapping.get(role, base)

    def _selector_literal(self, text: str) -> str:
        escaped = (
            text.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("`", "\\`")
            .replace("\n", "\\A ")
        )
        return f'"{escaped}"'

    def _xpath_literal(self, text: str) -> str:
        if "'" not in text:
            return f"'{text}'"
        if '"' not in text:
            return f'"{text}"'
        parts = text.split("'")
        tokens = []
        for idx, part in enumerate(parts):
            if part:
                tokens.append(f"'{part}'")
            if idx != len(parts) - 1:
                tokens.append('"\'"')
        return "concat(" + ", ".join(tokens) + ")"

    def _text_regex(self, text: str) -> re.Pattern[str]:
        return re.compile(re.escape(text), re.IGNORECASE)

    async def _resolve_data_testid(self, variants: Iterable[str]) -> Optional[Any]:
        selectors: List[str] = []
        seen = set()
        for variant in variants:
            collapsed = self._collapse_whitespace(variant).lower()
            if not collapsed:
                continue
            ascii_variant = collapsed.translate(self._SMART_TO_ASCII_TABLE)
            for value in {collapsed, ascii_variant}:
                dash = value.replace(" ", "-")
                underscore = value.replace(" ", "_")
                for selector in (
                    f'[data-testid="{dash}"]',
                    f'[data-testid="{underscore}"]',
                    f'[data-testid*="{value}"]',
                ):
                    if selector not in seen:
                        seen.add(selector)
                        selectors.append(selector)
        if not selectors:
            return None
        candidates = []
        for selector in selectors:
            try:
                candidates.append(self.page.locator(selector))
            except Exception as exc:
                log.debug("navigator_pro_data_testid_failed", selector=selector, error=str(exc))
        if not candidates:
            return None
        locator, _ = await self._first_matching_locator(candidates, strategy="data-testid")
        return locator

    def _record_locator_result(
        self,
        step,
        strategy: str,
        attempts: int,
        success: bool,
        start_time: float,
    ) -> None:
        duration_ms = int((perf_counter() - start_time) * 1000)
        log.debug(
            "navigator_pro_strategy",
            strategy=strategy,
            success=success,
            attempts=attempts,
            duration_ms=duration_ms,
            action=step.action,
            selector=step.selector,
            name=step.name,
        )

    async def _log_locator_diagnostics(self, step, variants: List[str]) -> None:
        try:
            sample_texts: List[str] = []
            if step.role:
                try:
                    sample_locator = self._page_get_by_role(step.role)
                    sample_texts = await sample_locator.all_inner_texts()
                except Exception:
                    sample_texts = []
            log.debug(
                "navigator_pro_locator_debug",
                action=step.action,
                role=step.role,
                selector=step.selector,
                name=step.name,
                variants=variants[:5],
                sample_texts=[self._collapse_whitespace(s) for s in sample_texts[:5]],
            )
        except Exception as exc:
            log.debug("navigator_pro_locator_debug_failed", error=str(exc))
