from __future__ import annotations

from pathlib import Path


class TraceController:
    def __init__(self, context) -> None:
        self.context = context

    async def start(self) -> None:
        await self.context.tracing.start(screenshots=True, snapshots=True, sources=False)

    async def stop(self, out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        await self.context.tracing.stop(path=str(out_path))


