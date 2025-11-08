"""Strategy Generator - Learns from failures and generates improved strategies."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from parallax.core.constitution import FailureStore
from parallax.core.logging import get_logger
from parallax.core.schemas import PlanStep

log = get_logger("strategy_generator")


class SelectorStrategy:
    """A selector strategy learned from failures."""
    
    def __init__(
        self,
        pattern: str,
        selector_type: str,
        success_rate: float = 0.0,
        usage_count: int = 0,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.pattern = pattern
        self.selector_type = selector_type  # "role", "data-testid", "css", "xpath", "text"
        self.success_rate = success_rate
        self.usage_count = usage_count
        self.context = context or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern": self.pattern,
            "selector_type": self.selector_type,
            "success_rate": self.success_rate,
            "usage_count": self.usage_count,
            "context": self.context,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SelectorStrategy:
        return cls(
            pattern=data["pattern"],
            selector_type=data["selector_type"],
            success_rate=data.get("success_rate", 0.0),
            usage_count=data.get("usage_count", 0),
            context=data.get("context", {}),
        )


class StrategyGenerator:
    """
    Generates selector strategies based on failure patterns.
    
    Learns from failures stored in FailureStore and generates improved
    selector strategies that can be used by Navigator and Interpreter.
    """
    
    def __init__(
        self,
        failure_store: Optional[FailureStore] = None,
        strategies_file: Optional[Path] = None,
    ):
        self.failure_store = failure_store
        self.strategies_file = strategies_file or Path("datasets/_strategies/strategies.json")
        self.strategies_file.parent.mkdir(parents=True, exist_ok=True)
        self._strategies: Dict[str, List[SelectorStrategy]] = {}
        self._load_strategies()
    
    def _load_strategies(self) -> None:
        """Load strategies from disk."""
        if not self.strategies_file.exists():
            return
        
        try:
            with self.strategies_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                for key, strategies_data in data.items():
                    self._strategies[key] = [
                        SelectorStrategy.from_dict(s) for s in strategies_data
                    ]
            log.info("strategies_loaded", count=sum(len(s) for s in self._strategies.values()))
        except Exception as e:
            log.warning("strategies_load_failed", error=str(e))
    
    def _save_strategies(self) -> None:
        """Save strategies to disk."""
        try:
            data = {
                key: [s.to_dict() for s in strategies]
                for key, strategies in self._strategies.items()
            }
            with self.strategies_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            log.debug("strategies_saved", count=sum(len(s) for s in self._strategies.values()))
        except Exception as e:
            log.warning("strategies_save_failed", error=str(e))
    
    def analyze_failures(self, limit: int = 50) -> Dict[str, Any]:
        """
        Analyze failures to identify patterns.
        
        Returns:
            Dictionary with failure patterns and statistics
        """
        if not self.failure_store:
            return {}
        
        failures = self.failure_store.get_failures(limit=limit)
        if not failures:
            return {}
        
        patterns = {
            "selector_failures": [],
            "action_failures": [],
            "navigation_failures": [],
            "auth_failures": [],
        }
        
        for failure in failures:
            failures_list = failure.get("failures", [])
            for f in failures_list:
                rule_name = f.get("rule_name", "")
                details = f.get("details", {})
                
                if "selector" in rule_name.lower() or "locator" in rule_name.lower():
                    patterns["selector_failures"].append({
                        "rule": rule_name,
                        "details": details,
                        "context": failure.get("context", {}),
                    })
                elif "action" in rule_name.lower():
                    patterns["action_failures"].append({
                        "rule": rule_name,
                        "details": details,
                        "context": failure.get("context", {}),
                    })
                elif "navigation" in rule_name.lower():
                    patterns["navigation_failures"].append({
                        "rule": rule_name,
                        "details": details,
                        "context": failure.get("context", {}),
                    })
                elif "auth" in rule_name.lower():
                    patterns["auth_failures"].append({
                        "rule": rule_name,
                        "details": details,
                        "context": failure.get("context", {}),
                    })
        
        return patterns
    
    def generate_selector_strategies(
        self,
        element_description: str,
        website_pattern: Optional[str] = None,
        failure_context: Optional[List[Dict[str, Any]]] = None,
        step: Optional[PlanStep] = None,
    ) -> List[SelectorStrategy]:
        """
        Generate selector strategies for an element.
        
        Args:
            element_description: Description of the element to find
            website_pattern: Pattern/domain of the website
            failure_context: Previous failure context
        
        Returns:
            List of selector strategies ordered by likely success
        """
        # Check for existing strategies
        step_key = ""
        if step:
            step_key = step.selector or step.name or ""
        cache_key = f"{website_pattern or 'generic'}:{element_description.lower()}:{step_key}"
        if cache_key in self._strategies:
            strategies = self._strategies[cache_key]
            # Sort by success rate
            strategies.sort(key=lambda s: s.success_rate, reverse=True)
            return strategies
        
        # Generate new strategies based on patterns
        base_strategies: List[SelectorStrategy] = []
        
        # Strategy 1: Role-based with name variants
        base_strategies.append(SelectorStrategy(
            pattern=element_description,
            selector_type="role",
            context={"use_name_variants": True, "step_key": step_key},
        ))
        
        # Strategy 2: Data-testid heuristics
        base_strategies.append(SelectorStrategy(
            pattern=element_description,
            selector_type="data-testid",
            context={"use_dash_underscore": True, "step_key": step_key},
        ))
        
        # Strategy 3: Text-based with regex
        base_strategies.append(SelectorStrategy(
            pattern=element_description,
            selector_type="text",
            context={"use_regex": True, "case_insensitive": True, "step_key": step_key},
        ))
        
        # Strategy 4: CSS selector with common patterns
        base_strategies.append(SelectorStrategy(
            pattern=element_description,
            selector_type="css",
            context={"use_common_patterns": True, "step_key": step_key},
        ))
        
        # Strategy 5: XPath with text matching
        base_strategies.append(SelectorStrategy(
            pattern=element_description,
            selector_type="xpath",
            context={"use_text_matching": True, "step_key": step_key},
        ))

        # Strategy 6: Search-specific heuristics
        search_tokens = [
            "search",
            "lookup",
            "find",
        ]
        element_lower = element_description.lower()
        step_selector = (step.selector or "").lower() if step and step.selector else ""
        strategies: List[SelectorStrategy] = []
        if any(token in element_lower for token in search_tokens) or "search" in step_selector:
            strategies.append(SelectorStrategy(
                pattern=element_description,
                selector_type="placeholder",
                context={"attribute": "placeholder", "includes": ["search", "find", "look"], "step_key": step_key},
            ))
            strategies.append(SelectorStrategy(
                pattern=element_description,
                selector_type="role_searchbox",
                context={"step_key": step_key},
            ))
            strategies.append(SelectorStrategy(
                pattern=element_description,
                selector_type="css_search",
                context={"selectors": ["input[type='search']", "input[role='searchbox']", "form input[type='text']"], "step_key": step_key},
            ))
            strategies.append(SelectorStrategy(
                pattern=element_description,
                selector_type="aria_label",
                context={"attribute": "aria-label", "includes": ["search", "find"], "step_key": step_key},
            ))
        
        # Append base strategies after specialized ones
        strategies.extend(base_strategies)

        # Store strategies
        self._strategies[cache_key] = strategies
        self._save_strategies()
        
        return strategies
    
    def record_strategy_result(
        self,
        strategy: SelectorStrategy,
        success: bool,
        element_description: Optional[str] = None,
        website_pattern: Optional[str] = None,
        step: Optional[PlanStep] = None,
    ) -> None:
        """
        Record the result of using a strategy.
        
        Updates success rate and usage count.
        """
        step_key = strategy.context.get("step_key", "")
        if step:
            step_key = step.selector or step.name or step_key
        cache_key = f"{website_pattern or 'generic'}:{(element_description or 'unknown').lower()}:{step_key}"
        
        if cache_key not in self._strategies:
            return
        
        # Find matching strategy
        for s in self._strategies[cache_key]:
            if (s.pattern == strategy.pattern and 
                s.selector_type == strategy.selector_type):
                s.usage_count += 1
                if success:
                    # Update success rate (exponential moving average)
                    s.success_rate = 0.9 * s.success_rate + 0.1 * 1.0
                else:
                    s.success_rate = 0.9 * s.success_rate + 0.1 * 0.0
                break
        
        self._save_strategies()
    
    def get_best_strategies(
        self,
        element_description: str,
        website_pattern: Optional[str] = None,
        limit: int = 3,
        step: Optional[PlanStep] = None,
    ) -> List[SelectorStrategy]:
        """
        Get the best strategies for an element based on historical success.
        
        Returns:
            List of strategies ordered by success rate
        """
        strategies = self.generate_selector_strategies(
            element_description,
            website_pattern,
            step=step,
        )
        
        # Sort by success rate (descending)
        strategies.sort(key=lambda s: s.success_rate, reverse=True)
        
        return strategies[:limit]
    
    def suggest_improved_step(
        self,
        failed_step: PlanStep,
        failure_reason: str,
        website_pattern: Optional[str] = None,
    ) -> Optional[PlanStep]:
        """
        Suggest an improved step based on failure.
        
        Args:
            failed_step: The step that failed
            failure_reason: Reason for failure
            website_pattern: Pattern/domain of the website
        
        Returns:
            Improved step or None if no improvement can be suggested
        """
        if not failed_step.name and not failed_step.selector:
            return None
        
        element_description = failed_step.name or failed_step.selector or ""
        
        # Get best strategies
        strategies = self.get_best_strategies(
            element_description,
            website_pattern,
            limit=1,
            step=failed_step,
        )
        
        if not strategies:
            return None
        
        original_selector = failed_step.selector
        original_role = failed_step.role

        for strategy in strategies:
            improved_step = PlanStep(
                action=failed_step.action,
                target=failed_step.target,
                role=failed_step.role,
                name=failed_step.name,
                selector=failed_step.selector,
                value=failed_step.value,
                start_selector=failed_step.start_selector,
                end_selector=failed_step.end_selector,
                file_path=failed_step.file_path,
                option_value=failed_step.option_value,
            )

            if strategy.selector_type == "role" and failed_step.name:
                improved_step.role = failed_step.role or "button"
            elif strategy.selector_type == "data-testid" and failed_step.name:
                base = failed_step.name.lower().replace(" ", "-")
                improved_step.selector = f'[data-testid="{base}"]'
            elif strategy.selector_type == "text" and failed_step.name:
                improved_step.selector = None
            elif strategy.selector_type == "css" and failed_step.name:
                base = failed_step.name.lower().replace(" ", "-")
                improved_step.selector = f'button[data-testid="{base}"], [data-testid="{base}"]'
            elif strategy.selector_type == "placeholder":
                improved_step.selector = "input[placeholder*='search' i], input[placeholder*='find' i], input[placeholder*='wiki' i]"
            elif strategy.selector_type == "role_searchbox":
                improved_step.role = "searchbox"
                improved_step.selector = None
            elif strategy.selector_type == "css_search":
                selectors = strategy.context.get("selectors", [])
                if selectors:
                    improved_step.selector = ", ".join(selectors + ["input#searchInput", "form input[name='search']"])
            elif strategy.selector_type == "aria_label":
                improved_step.selector = "input[aria-label*='search' i], input[aria-label*='find' i], input[aria-label*='wiki' i]"

            if improved_step.selector != original_selector or improved_step.role != original_role:
                return improved_step

        return None

