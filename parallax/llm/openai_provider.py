from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, Optional

try:
    from aiolimiter import AsyncLimiter
except ImportError:
    # Fallback if aiolimiter not installed
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
    # Fallback if tenacity not installed - create no-op decorator
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

from parallax.core.exceptions import (
    LLMAPIError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from parallax.core.cost_tracker import CostTracker, PRICING
from parallax.core.logging import get_logger
from parallax.core.schemas import ExecutionPlan, PlanStep
from parallax.llm.utils import extract_json_from_content

log = get_logger("openai")

try:
    from openai import AsyncOpenAI  # type: ignore
    from openai import RateLimitError, APIError  # type: ignore
except Exception:  # pragma: no cover
    AsyncOpenAI = None  # type: ignore
    RateLimitError = Exception  # type: ignore
    APIError = Exception  # type: ignore


class OpenAIPlanner:
    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        timeout: float = 30.0,
        max_retries: int = 3,
        rate_limit_per_minute: int = 50,
    ) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAIPlanner")
        if AsyncOpenAI is None:
            raise RuntimeError("openai package not installed")
        self.client = AsyncOpenAI(api_key=api_key, timeout=timeout)
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limiter = AsyncLimiter(max_rate=rate_limit_per_minute, time_period=60)
        self.cost_tracker = CostTracker()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((LLMTimeoutError, LLMRateLimitError)),
        reraise=True,
    )
    async def generate_plan(self, task: str, context: Dict) -> ExecutionPlan:
        system_prompt = """You are a web automation planner. Generate a JSON plan with ordered steps.

Actions:
- navigate: {"action": "navigate", "target": "https://example.com"}
- click: {"action": "click", "role": "button", "name": "Create"} or {"action": "click", "selector": "button[data-testid='submit']"}
- type: {"action": "type", "selector": "input[name='title']", "value": "My Title"}
- submit: {"action": "submit", "selector": "form button[type='submit']"}
- select: {"action": "select", "selector": "select[name='status']", "value": "active"} or {"action": "select", "selector": "select", "option_value": "option1"}
- drag: {"action": "drag", "start_selector": "#item1", "end_selector": "#dropzone"} or {"action": "drag", "start_selector": "#item1", "target": "#dropzone"}
- upload: {"action": "upload", "selector": "input[type='file']", "file_path": "/path/to/file.pdf"} or {"action": "upload", "selector": "input[type='file']", "value": "/path/to/file.pdf"}
- hover: {"action": "hover", "selector": "button.menu", "role": "button", "name": "Menu"}
- double_click: {"action": "double_click", "selector": "#item", "role": "button", "name": "Item"}
- right_click: {"action": "right_click", "selector": "#context-menu", "role": "button"}
- fill: {"action": "fill", "selector": "input[name='email']", "value": "user@example.com"}
- check: {"action": "check", "selector": "input[type='checkbox']", "name": "Accept Terms"}
- uncheck: {"action": "uncheck", "selector": "input[type='checkbox']", "name": "Newsletter"}
- focus: {"action": "focus", "selector": "input[name='search']"}
- blur: {"action": "blur", "selector": "input[name='search']"}
- key_press: {"action": "key_press", "value": "Enter"} or {"action": "press_key", "value": "Escape"}
- wait: {"action": "wait", "value": "2s"} or {"action": "wait", "value": "1000ms"}
- scroll: {"action": "scroll", "value": "down"} or {"action": "scroll", "selector": "#section"}
- go_back: {"action": "go_back"}
- go_forward: {"action": "go_forward"}
- reload: {"action": "reload"}
- screenshot: {"action": "screenshot", "value": "screenshot.png"}
- evaluate: {"action": "evaluate", "value": "document.title"}

Selector priority: role+name > label > placeholder > data-testid > CSS selector.

Examples:
Task: "Create a project in Linear"
{
  "steps": [
    {"action": "navigate", "target": "https://linear.app"},
    {"action": "click", "role": "button", "name": "Create"},
    {"action": "click", "role": "menuitem", "name": "Project"},
    {"action": "type", "selector": "input[name='name']", "value": "Q4 Plan"},
    {"action": "submit", "selector": "button[type='submit']"}
  ]
}

Task: "Filter database in Notion"
{
  "steps": [
    {"action": "navigate", "target": "https://notion.so"},
    {"action": "click", "role": "button", "name": "Filter"},
    {"action": "click", "role": "combobox", "name": "Property"},
    {"action": "click", "role": "option", "name": "Status"},
    {"action": "click", "role": "button", "name": "Apply"}
  ]
}

Task: "Explore all tabs on a website"
{
  "steps": [
    {"action": "navigate", "target": "https://example.com"},
    {"action": "wait", "value": "1s"},
    {"action": "click", "role": "link", "name": "About"},
    {"action": "wait", "value": "1s"},
    {"action": "navigate", "target": "https://example.com"},
    {"action": "click", "role": "link", "name": "Services"},
    {"action": "wait", "value": "1s"},
    {"action": "navigate", "target": "https://example.com"},
    {"action": "click", "role": "link", "name": "Contact"},
    {"action": "wait", "value": "1s"}
  ]
}

Task: "Navigate to softlight.com and explore all tabs on that website"
{
  "steps": [
    {"action": "navigate", "target": "https://softlight.com"},
    {"action": "wait", "value": "2s"},
    {"action": "click", "role": "link", "name": "We're hiring"},
    {"action": "wait", "value": "2s"},
    {"action": "navigate", "target": "https://softlight.com"},
    {"action": "click", "role": "link", "name": "Join waitlist"},
    {"action": "wait", "value": "1s"}
  ]
}

Task: "Navigate to a website and explore the full website"
{
  "steps": [
    {"action": "navigate", "target": "https://example.com"},
    {"action": "wait", "value": "2s"},
    {"action": "scroll", "value": "down"},
    {"action": "wait", "value": "1s"},
    {"action": "click", "role": "link", "name": "About"},
    {"action": "wait", "value": "2s"},
    {"action": "navigate", "target": "https://example.com"},
    {"action": "click", "role": "link", "name": "Services"},
    {"action": "wait", "value": "2s"},
    {"action": "navigate", "target": "https://example.com"},
    {"action": "scroll", "value": "down"},
    {"action": "wait", "value": "1s"}
  ]
}

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

IMPORTANT: If a Start URL is provided in the task context, ALWAYS use that URL for navigation steps. Never use placeholder URLs like example.com unless explicitly requested.
Generate a plan for the user task."""
        
        examples = [
            {
                "role": "user",
                "content": "Create a project in Linear"
            },
            {
                "role": "assistant",
                "content": '{"steps": [{"action": "navigate", "target": "https://linear.app"}, {"action": "click", "role": "button", "name": "Create"}, {"action": "click", "role": "menuitem", "name": "Project"}, {"action": "type", "selector": "input[name=\'name\']", "value": "Q4 Plan"}, {"action": "submit", "selector": "button[type=\'submit\']"}]}'
            }
        ]
        
        # Build user message with context
        user_message = task
        if context.get("start_url"):
            user_message = f"Task: {task}\nStart URL: {context['start_url']}\n\nIMPORTANT: Use the Start URL provided above for navigation steps. Do not use example.com or other placeholder URLs."
        
        async with self.rate_limiter:
            try:
                resp = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            *examples,
                            {"role": "user", "content": user_message},
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.2,
                        max_tokens=1200,
                    ),
                    timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                log.error("llm_timeout", provider="openai", timeout=self.timeout)
                raise LLMTimeoutError("openai", self.timeout) from None
            except RateLimitError as e:
                retry_after = getattr(e, "retry_after", None)
                log.warning("rate_limit_exceeded", provider="openai", retry_after=retry_after)
                raise LLMRateLimitError("openai", retry_after) from e
            except APIError as e:
                status_code = getattr(e, "status_code", None)
                log.error("api_error", provider="openai", status_code=status_code, error=str(e))
                raise LLMAPIError("openai", status_code, str(e), retryable=status_code and status_code >= 500) from e
        
        if not resp.choices:
            raise LLMAPIError("openai", None, "No choices in OpenAI response", retryable=False)
        
        # Extract token usage and calculate cost
        usage = getattr(resp, 'usage', None)
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        
        # Track cost
        self.cost_tracker.track_llm_call("openai", self.model, input_tokens, output_tokens)
        
        content = resp.choices[0].message.content or "{}"
        try:
            data = extract_json_from_content(content)
        except (ValueError, json.JSONDecodeError) as e:
            log.error("json_extraction_failed", error=str(e), content_preview=content[:200])
            raise LLMAPIError("openai", None, f"Failed to extract JSON from LLM response: {e}", retryable=False) from e
        
        json_loader = context.get("json_loader", lambda x: json.loads(x))
        # Use extracted data or try json_loader as fallback
        if not isinstance(data, dict):
            data = json_loader(content) if content else {}
        steps = [PlanStep(**s) for s in data.get("steps", [])]
        return ExecutionPlan(steps=steps)


