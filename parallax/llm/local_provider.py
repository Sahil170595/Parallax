from __future__ import annotations

import json
import os
from typing import Dict

from parallax.core.schemas import ExecutionPlan, PlanStep


class LocalPlanner:
    def __init__(self, model: str | None = None, host: str | None = None) -> None:
        self.model = model or os.getenv("LOCAL_MODEL", "llama3.1:8b")
        self.host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self._client = None

    async def _get_client(self):
        if self._client is None:
            try:
                import httpx  # type: ignore
                self._client = httpx.AsyncClient(base_url=self.host, timeout=30.0)
            except ImportError:
                raise RuntimeError("httpx required for LocalPlanner (pip install httpx)")
        return self._client

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
- wait: {{"action": "wait", "value": "2s"}}
- scroll: {{"action": "scroll", "value": "down"}} or {{"action": "scroll", "selector": "#section"}}

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
        
        try:
            resp = await client.post(
                "/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            content = resp.json().get("response", "")
            # Extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            # Try to find JSON object
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                content = content[start:end]
            data = json.loads(content)
            steps = [PlanStep(**s) for s in data.get("steps", [])]
            if not steps:
                # Fallback: simple navigate
                steps = [PlanStep(action="navigate", target=context.get("start_url", "https://example.com"))]
            return ExecutionPlan(steps=steps)
        except Exception as e:
            # Fallback: minimal plan
            return ExecutionPlan(
                steps=[PlanStep(action="navigate", target=context.get("start_url", "https://example.com"))]
            )


