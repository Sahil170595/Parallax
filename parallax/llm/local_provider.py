from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, Optional

try:
    from aiolimiter import AsyncLimiter
except ImportError:
    class AsyncLimiter:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass

try:
    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )
except ImportError:
    def retry(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def stop_after_attempt(*args):
        pass
    def wait_exponential(*args, **kwargs):
        pass
    def retry_if_exception_type(*args):
        pass

from parallax.core.exceptions import LLMAPIError, LLMTimeoutError
from parallax.core.cost_tracker import CostTracker
from parallax.core.logging import get_logger
from parallax.core.schemas import ExecutionPlan, PlanStep
from parallax.llm.utils import extract_json_from_content

log = get_logger("local")


class LocalPlanner:
    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        rate_limit_per_minute: int = 30,
    ) -> None:
        self.model = model or os.getenv("LOCAL_MODEL", "llama3.1:8b")
        self.host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limiter = AsyncLimiter(max_rate=rate_limit_per_minute, time_period=60)
        self._client: Optional[Any] = None
        self.cost_tracker = CostTracker()

    async def _get_client(self):
        if self._client is None:
            try:
                import httpx  # type: ignore
                self._client = httpx.AsyncClient(base_url=self.host, timeout=30.0)
            except ImportError:
                raise RuntimeError("httpx required for LocalPlanner (pip install httpx)")
        return self._client
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup resources."""
        await self.close()
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass  # Ignore errors during cleanup
            finally:
                self._client = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((LLMTimeoutError, ConnectionError)),
        reraise=True,
    )
    async def generate_plan(self, task: str, context: Dict) -> ExecutionPlan:
        client = await self._get_client()
        start_url = context.get("start_url", "https://example.com")
        prompt = f"""You are a web automation planner. Generate a JSON plan with ordered steps.

Task: {task}
Start URL: {start_url}

Available Actions:
- navigate: {{"action": "navigate", "target": "https://example.com"}}
- click: {{"action": "click", "role": "button", "name": "Create"}} or {{"action": "click", "role": "link", "name": "About"}} or {{"action": "click", "selector": "button[data-testid='submit']"}}
- type: {{"action": "type", "selector": "input[name='title']", "value": "My Title"}}
- submit: {{"action": "submit", "selector": "button[type='submit']"}}
- select: {{"action": "select", "selector": "select[name='status']", "value": "active"}} or {{"action": "select", "selector": "select", "option_value": "option1"}}
- drag: {{"action": "drag", "start_selector": "#item1", "end_selector": "#dropzone"}} or {{"action": "drag", "start_selector": "#item1", "target": "#dropzone"}}
- upload: {{"action": "upload", "selector": "input[type='file']", "file_path": "/path/to/file.pdf"}} or {{"action": "upload", "selector": "input[type='file']", "value": "/path/to/file.pdf"}}
- hover: {{"action": "hover", "selector": "button.menu", "role": "button", "name": "Menu"}}
- double_click: {{"action": "double_click", "selector": "#item", "role": "button", "name": "Item"}}
- right_click: {{"action": "right_click", "selector": "#context-menu", "role": "button"}}
- fill: {{"action": "fill", "selector": "input[name='email']", "value": "user@example.com"}}
- check: {{"action": "check", "selector": "input[type='checkbox']", "name": "Accept Terms"}}
- uncheck: {{"action": "uncheck", "selector": "input[type='checkbox']", "name": "Newsletter"}}
- focus: {{"action": "focus", "selector": "input[name='search']"}}
- blur: {{"action": "blur", "selector": "input[name='search']"}}
- key_press: {{"action": "key_press", "value": "Enter"}} or {{"action": "press_key", "value": "Escape"}}
- wait: {{"action": "wait", "value": "2s"}} or {{"action": "wait", "value": "1000ms"}}
- scroll: {{"action": "scroll", "value": "down"}} or {{"action": "scroll", "selector": "#section"}}
- go_back: {{"action": "go_back"}}
- go_forward: {{"action": "go_forward"}}
- reload: {{"action": "reload"}}
- screenshot: {{"action": "screenshot", "value": "screenshot.png"}}
- evaluate: {{"action": "evaluate", "value": "document.title"}}

Examples:
Task: "Explore all tabs on a website"
{{
  "steps": [
    {{"action": "navigate", "target": "{start_url}"}},
    {{"action": "wait", "value": "1s"}},
    {{"action": "click", "role": "link", "name": "About"}},
    {{"action": "wait", "value": "1s"}},
    {{"action": "navigate", "target": "{start_url}"}},
    {{"action": "click", "role": "link", "name": "Services"}},
    {{"action": "wait", "value": "1s"}},
    {{"action": "navigate", "target": "{start_url}"}},
    {{"action": "click", "role": "link", "name": "Contact"}},
    {{"action": "wait", "value": "1s"}}
  ]
}}

Task: "Navigate to softlight.com and explore all tabs on that website"
{{
  "steps": [
    {{"action": "navigate", "target": "https://softlight.com"}},
    {{"action": "wait", "value": "2s"}},
    {{"action": "click", "role": "link", "name": "We're hiring"}},
    {{"action": "wait", "value": "2s"}},
    {{"action": "navigate", "target": "https://softlight.com"}},
    {{"action": "click", "role": "link", "name": "Join waitlist"}},
    {{"action": "wait", "value": "1s"}}
  ]
}}

Task: "Navigate to a website and explore the full website"
{{
  "steps": [
    {{"action": "navigate", "target": "{start_url}"}},
    {{"action": "wait", "value": "2s"}},
    {{"action": "scroll", "value": "down"}},
    {{"action": "wait", "value": "1s"}},
    {{"action": "click", "role": "link", "name": "About"}},
    {{"action": "wait", "value": "2s"}},
    {{"action": "navigate", "target": "{start_url}"}},
    {{"action": "click", "role": "link", "name": "Services"}},
    {{"action": "wait", "value": "2s"}},
    {{"action": "navigate", "target": "{start_url}"}},
    {{"action": "scroll", "value": "down"}},
    {{"action": "wait", "value": "1s"}}
  ]
}}

EXPLORATION STRATEGY:
When the task contains keywords like "explore", "all tabs", "full website", "navigate through", or "find":
1. ALWAYS start by navigating to the start URL
2. Add a wait step (1-2s) after navigation to let the page load
3. Systematically identify and click on ALL navigation elements:
   - Main navigation links (header/nav menu)
   - Tab buttons
   - Menu items
   - Primary call-to-action buttons
   - Important content links (not footer/social links unless explicitly requested)
4. For each click, navigate back to the start URL before clicking the next element
5. Include wait steps between actions to allow pages to load
6. For "full website" or "explore the site", also include scroll actions to discover more content
7. Prioritize main navigation elements over footer/social links

When exploring, think about what a user would see on screen:
- Navigation bars at the top
- Tab buttons
- Menu dropdowns
- Primary action buttons
- Main content links

Generate a comprehensive plan that explores all visible navigation elements systematically.
Return JSON with "steps" array: {{"steps": [...]}}"""
        
        async with self.rate_limiter:
            try:
                resp = await asyncio.wait_for(
                    client.post(
                        "/api/generate",
                        json={"model": self.model, "prompt": prompt, "stream": False},
                    ),
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                response_data = resp.json()
                content = response_data.get("response", "")
                
                # Extract token usage from Ollama response (if available)
                prompt_eval_count = response_data.get("prompt_eval_count", 0)
                eval_count = response_data.get("eval_count", 0)
                self.cost_tracker.track_llm_call("local", self.model, prompt_eval_count, eval_count)
                
                try:
                    data = extract_json_from_content(content)
                except (ValueError, json.JSONDecodeError) as e:
                    log.warning("json_extraction_failed", error=str(e), content_preview=content[:200])
                    # Fallback: minimal plan
                    return ExecutionPlan(
                        steps=[PlanStep(action="navigate", target=context.get("start_url", "https://example.com"))]
                    )
                steps = [PlanStep(**s) for s in data.get("steps", [])]
                if not steps:
                    # Fallback: simple navigate
                    steps = [PlanStep(action="navigate", target=context.get("start_url", "https://example.com"))]
                return ExecutionPlan(steps=steps)
            except asyncio.TimeoutError:
                log.error("llm_timeout", provider="local", timeout=self.timeout)
                raise LLMTimeoutError("local", self.timeout) from None
            except Exception as e:
                log.error("local_planner_failed", error=str(e), error_type=type(e).__name__)
                # For local provider, we're more lenient - return fallback plan
                # but still log the error
                if isinstance(e, ConnectionError):
                    raise LLMAPIError("local", None, f"Connection error: {e}", retryable=True) from e
                # Fallback: minimal plan
                return ExecutionPlan(
                    steps=[PlanStep(action="navigate", target=context.get("start_url", "https://example.com"))]
                )


