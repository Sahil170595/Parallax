"""Integration test for Local provider (Ollama) - no API keys needed."""
import pytest
from parallax.llm.local_provider import LocalPlanner
from parallax.core.schemas import ExecutionPlan


@pytest.mark.asyncio
async def test_local_provider_fallback():
    """Test Local provider falls back gracefully when Ollama is not available."""
    planner = LocalPlanner()
    # This should return a minimal plan even if Ollama is not running
    plan = await planner.generate_plan("Create a project", {"start_url": "https://example.com"})
    assert isinstance(plan, ExecutionPlan)
    assert len(plan.steps) > 0
    assert plan.steps[0].action == "navigate"
    assert plan.steps[0].target == "https://example.com"

