from __future__ import annotations

import os
from typing import Any, Dict

from parallax.core.schemas import ExecutionPlan, PlanStep

try:
    import anthropic  # type: ignore
except Exception:  # pragma: no cover
    anthropic = None  # type: ignore


class AnthropicPlanner:
    def __init__(self, model: str = "claude-3-5-sonnet-latest") -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for AnthropicPlanner")
        if anthropic is None:
            raise RuntimeError("anthropic package not installed")
        self.client = anthropic.Anthropic(api_key=api_key)
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

Generate a plan for the user task."""
        
        msg = await self.client.messages.create(
            model=self.model,
            max_tokens=1200,
            temperature=0.2,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"Task: {task}\n\nGenerate a JSON plan with a 'steps' array."
                }
            ],
        )
        content = "".join(part.text for part in msg.content if getattr(part, "text", None))
        json_loader = context.get("json_loader", lambda x: __import__("json").loads(x))
        # Extract JSON from markdown code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        data = json_loader(content)
        steps = [PlanStep(**s) for s in data.get("steps", [])]
        return ExecutionPlan(steps=steps)


