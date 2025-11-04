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
        prompt = f"""You are a web automation planner. Generate a JSON plan.

Task: {task}

Actions:
- navigate: {{"action": "navigate", "target": "https://example.com"}}
- click: {{"action": "click", "role": "button", "name": "Create"}}
- type: {{"action": "type", "selector": "input[name='title']", "value": "My Title"}}
- submit: {{"action": "submit", "selector": "button[type='submit']"}}

Return JSON: {{"steps": [...]}}

Start URL: {context.get("start_url", "https://example.com")}"""
        
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


