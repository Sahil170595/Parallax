from __future__ import annotations

import os
from typing import Any, Dict

from parallax.core.schemas import ExecutionPlan, PlanStep

try:
    from openai import AsyncOpenAI  # type: ignore
except Exception:  # pragma: no cover
    AsyncOpenAI = None  # type: ignore


class OpenAIPlanner:
    def __init__(self, model: str = "gpt-4.1-mini") -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAIPlanner")
        if AsyncOpenAI is None:
            raise RuntimeError("openai package not installed")
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate_plan(self, task: str, context: Dict) -> ExecutionPlan:
        system_prompt = """You are a web automation planner. Generate a JSON plan with ordered steps.

Actions:
- navigate: {"action": "navigate", "target": "https://example.com"}
- click: {"action": "click", "role": "button", "name": "Create"} or {"action": "click", "selector": "button[data-testid='submit']"}
- type: {"action": "type", "selector": "input[name='title']", "value": "My Title"}
- submit: {"action": "submit", "selector": "form button[type='submit']"}

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
        
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                *examples,
                {"role": "user", "content": task},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=1200,
        )
        content = resp.choices[0].message.content or "{}"
        json_loader = context.get("json_loader", lambda x: __import__("json").loads(x))
        data = json_loader(content)
        steps = [PlanStep(**s) for s in data.get("steps", [])]
        return ExecutionPlan(steps=steps)


