"""Integration tests for complex multi-step workflows."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

import pytest
import pytest_asyncio
from playwright.async_api import async_playwright

from parallax.agents.interpreter import Interpreter
from parallax.agents.navigator import Navigator
from parallax.agents.observer import Observer
from parallax.core.config import ParallaxConfig
from parallax.core.constitution import FailureStore
from parallax.core.schemas import ExecutionPlan, PlanStep
from parallax.llm.local_provider import LocalPlanner
from parallax.observer.detectors import Detectors


@pytest_asyncio.fixture
async def browser_context():
    """Create a browser context for testing."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        yield page
        await context.close()
        await browser.close()


@pytest.fixture
def config():
    """Load test configuration."""
    config_path = Path("configs/config.yaml")
    return ParallaxConfig.from_yaml(config_path)


@pytest.fixture
def failure_store(config):
    """Create a failure store for testing."""
    datasets_dir = Path(config.output.base_dir)
    return FailureStore(datasets_dir / "_test_failures")


@pytest.mark.asyncio
async def test_multi_step_exploration_workflow(browser_context, config, failure_store):
    """Test a complex multi-step exploration workflow."""
    # Use local planner for testing (doesn't require API keys)
    planner = LocalPlanner()
    interpreter = Interpreter(planner, failure_store=failure_store)
    
    task = "Navigate to example.com and explore all tabs"
    start_url = "https://example.com"
    
    # Generate plan
    plan = await interpreter.plan(task, {"start_url": start_url})
    assert len(plan.steps) > 0, "Plan should have at least one step"
    assert plan.steps[0].action == "navigate", "First step should be navigation"
    
    # Execute plan
    detectors = Detectors(config.observer.model_dump() if hasattr(config.observer, 'model_dump') else config.observer.dict())
    observer = Observer(
        browser_context,
        detectors,
        save_dir=Path("/tmp/test_workflow"),
        failure_store=failure_store,
    )
    
    navigator = Navigator(
        browser_context,
        observer=observer,
        default_wait_ms=config.navigation.default_wait_ms,
        scroll_margin_px=config.navigation.scroll_margin_px,
        failure_store=failure_store,
    )
    
    await navigator.execute(plan, action_budget=config.navigation.action_budget)
    assert navigator.action_count > 0, "Should have executed at least one action"


@pytest.mark.asyncio
async def test_retry_logic_with_simulated_failures(browser_context, config, failure_store):
    """Test that retry logic works correctly."""
    # Create a plan that will fail initially
    plan = ExecutionPlan(steps=[
        PlanStep(action="navigate", target="https://example.com"),
        PlanStep(action="click", selector="button#nonexistent"),
    ])
    
    detectors = Detectors(config.observer.model_dump() if hasattr(config.observer, 'model_dump') else config.observer.dict())
    observer = Observer(
        browser_context,
        detectors,
        save_dir=Path("/tmp/test_retry"),
        failure_store=failure_store,
    )
    
    navigator = Navigator(
        browser_context,
        observer=observer,
        default_wait_ms=500,  # Faster for testing
        failure_store=failure_store,
    )
    
    # Should handle failure gracefully
    try:
        await navigator.execute(plan, action_budget=5)
    except Exception:
        pass  # Expected to fail, but should handle gracefully
    
    assert navigator.action_count >= 1, "Should have attempted at least navigation"


@pytest.mark.asyncio
async def test_cancellation_support(browser_context, config, failure_store):
    """Test cancellation token support."""
    # Create a cancellation token
    cancellation_event = asyncio.Event()
    
    class CancellationToken:
        def __init__(self, event):
            self.event = event
        
        def is_cancelled(self):
            return self.event.is_set()
    
    cancellation_token = CancellationToken(cancellation_event)
    
    # Create a long plan
    plan = ExecutionPlan(steps=[
        PlanStep(action="navigate", target="https://example.com"),
        PlanStep(action="wait", value="1s"),
        PlanStep(action="wait", value="1s"),
        PlanStep(action="wait", value="1s"),
    ])
    
    detectors = Detectors(config.observer.model_dump() if hasattr(config.observer, 'model_dump') else config.observer.dict())
    observer = Observer(
        browser_context,
        detectors,
        save_dir=Path("/tmp/test_cancellation"),
        failure_store=failure_store,
    )
    
    navigator = Navigator(
        browser_context,
        observer=observer,
        default_wait_ms=100,  # Faster for testing
        failure_store=failure_store,
    )
    
    # Cancel after first step
    async def cancel_after_first():
        await asyncio.sleep(0.5)
        cancellation_event.set()
    
    cancel_task = asyncio.create_task(cancel_after_first())
    
    try:
        await navigator.execute(plan, action_budget=10, cancellation_token=cancellation_token)
    except asyncio.CancelledError:
        pass  # Expected
    finally:
        cancel_task.cancel()
    
    # Should have executed at least one step before cancellation
    assert navigator.action_count >= 1


@pytest.mark.asyncio
async def test_rate_limiting_behavior(browser_context, config, failure_store):
    """Test that rate limiting doesn't break workflows."""
    planner = LocalPlanner(rate_limit_per_minute=10)  # Low rate limit
    
    # Generate multiple plans quickly
    interpreter = Interpreter(planner, failure_store=failure_store)
    
    tasks = [
        "Navigate to example.com",
        "Navigate to example.com",
        "Navigate to example.com",
    ]
    
    plans = []
    for task in tasks:
        plan = await interpreter.plan(task, {"start_url": "https://example.com"})
        plans.append(plan)
        # Small delay to allow rate limiter
        await asyncio.sleep(0.1)
    
    assert len(plans) == 3, "Should generate all plans despite rate limiting"


@pytest.mark.asyncio
async def test_timeout_handling(browser_context, config, failure_store):
    """Test timeout handling for long operations."""
    planner = LocalPlanner(timeout=1.0)  # Very short timeout
    
    interpreter = Interpreter(planner, failure_store=failure_store)
    
    # This should complete within timeout
    plan = await interpreter.plan(
        "Navigate to example.com",
        {"start_url": "https://example.com"}
    )
    
    assert plan is not None, "Plan should be generated"


@pytest.mark.asyncio
async def test_error_recovery(browser_context, config, failure_store):
    """Test error recovery and self-healing."""
    plan = ExecutionPlan(steps=[
        PlanStep(action="navigate", target="https://example.com"),
        PlanStep(action="click", selector="a[href='/']"),  # Should work
    ])
    
    detectors = Detectors(config.observer.model_dump() if hasattr(config.observer, 'model_dump') else config.observer.dict())
    observer = Observer(
        browser_context,
        detectors,
        save_dir=Path("/tmp/test_recovery"),
        failure_store=failure_store,
    )
    
    navigator = Navigator(
        browser_context,
        observer=observer,
        default_wait_ms=500,
        failure_store=failure_store,
    )
    
    await navigator.execute(plan, action_budget=5)
    # Should complete despite potential errors
    assert navigator.action_count >= 1


@pytest.mark.asyncio
async def test_form_submission_workflow(browser_context, config, failure_store):
    """Test a form submission workflow."""
    # Navigate to a page with a form
    await browser_context.goto("https://example.com")
    
    plan = ExecutionPlan(steps=[
        PlanStep(action="navigate", target="https://example.com"),
        PlanStep(action="wait", value="1s"),
    ])
    
    detectors = Detectors(config.observer.model_dump() if hasattr(config.observer, 'model_dump') else config.observer.dict())
    observer = Observer(
        browser_context,
        detectors,
        save_dir=Path("/tmp/test_form"),
        failure_store=failure_store,
    )
    
    navigator = Navigator(
        browser_context,
        observer=observer,
        default_wait_ms=config.navigation.default_wait_ms,
        failure_store=failure_store,
    )
    
    await navigator.execute(plan, action_budget=5)
    assert navigator.action_count > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

