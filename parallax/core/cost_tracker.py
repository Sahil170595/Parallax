"""Cost tracking for LLM API calls."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Optional

from prometheus_client import Counter, Histogram

from parallax.core.logging import get_logger

log = get_logger("cost_tracker")

# Cost tracking metrics
llm_cost_total = Counter(
    "parallax_llm_cost_total",
    "Total cost of LLM API calls",
    ["provider", "model"]
)

llm_cost_per_call = Histogram(
    "parallax_llm_cost_per_call",
    "Cost per LLM API call",
    ["provider", "model"],
    buckets=[0.001, 0.01, 0.1, 1.0, 10.0, 100.0]
)


# Pricing per 1M tokens (as of November 2025, approximate)
# Latest models: GPT-5 (best performance), GPT-4.1-mini (cost-effective), GPT-4o-mini (alternative)
PRICING: Dict[str, Dict[str, Dict[str, float]]] = {
    "openai": {
        "gpt-5": {"input": 1.25, "output": 5.00},  # Latest flagship model (released Aug 2025)
        "gpt-4.1-mini": {"input": 0.15, "output": 0.60},  # Cost-effective with good performance
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},  # Alternative cost-effective option
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    },
    "anthropic": {
        "claude-3-5-sonnet-latest": {"input": 3.00, "output": 15.00},
        "claude-3-opus": {"input": 15.00, "output": 75.00},
        "claude-3-sonnet": {"input": 3.00, "output": 15.00},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
    },
    "local": {
        "default": {"input": 0.0, "output": 0.0},  # Local models are free
    },
}


class CostTracker:
    """Tracks LLM API costs per provider and model."""
    
    def __init__(self):
        self.costs: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.total_cost: float = 0.0
    
    def track_llm_call(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Track an LLM API call and calculate cost.
        
        Args:
            provider: LLM provider name (openai, anthropic, local)
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        
        Returns:
            Cost in USD
        """
        # Get pricing for this provider/model
        pricing = PRICING.get(provider, {}).get(model)
        if not pricing:
            # Try to find default or closest match
            if provider == "local":
                pricing = PRICING["local"]["default"]
            else:
                # Use a default pricing (conservative estimate)
                log.warning(
                    "unknown_pricing",
                    provider=provider,
                    model=model,
                    message="Using default pricing estimate"
                )
                pricing = {"input": 1.0, "output": 3.0}
        
        # Calculate cost
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost
        
        # Track costs
        self.costs[provider][model] += total_cost
        self.total_cost += total_cost
        
        # Update metrics
        llm_cost_total.labels(provider=provider, model=model).inc(total_cost)
        llm_cost_per_call.labels(provider=provider, model=model).observe(total_cost)
        
        log.info(
            "llm_cost_tracked",
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=total_cost,
            total_cost_usd=self.total_cost
        )
        
        return total_cost
    
    def get_cost_summary(self) -> Dict[str, any]:
        """Get a summary of all tracked costs."""
        summary = {
            "total_cost_usd": self.total_cost,
            "by_provider": {}
        }
        
        for provider, models in self.costs.items():
            provider_total = sum(models.values())
            summary["by_provider"][provider] = {
                "total_cost_usd": provider_total,
                "by_model": dict(models)
            }
        
        return summary
    
    def reset(self) -> None:
        """Reset all tracked costs."""
        self.costs.clear()
        self.total_cost = 0.0
        log.info("cost_tracker_reset")


# Global cost tracker instance
_global_tracker: Optional[CostTracker] = None


def get_cost_tracker() -> CostTracker:
    """Get the global cost tracker instance."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = CostTracker()
    return _global_tracker


def reset_cost_tracker() -> None:
    """Reset the global cost tracker."""
    global _global_tracker
    if _global_tracker is not None:
        _global_tracker.reset()

