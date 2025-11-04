from __future__ import annotations

from typing import Protocol

from parallax.core.schemas import ExecutionPlan


class PlannerProvider(Protocol):
    async def generate_plan(self, task: str, context: dict) -> ExecutionPlan:
        ...


