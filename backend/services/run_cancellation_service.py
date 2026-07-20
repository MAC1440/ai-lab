from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class CancelResult:
    run_id: str
    cancelled: bool


class RunCancellationService:
    """Tracks only live stream tasks; completed runs leave no retained state."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[object]] = {}
        self._lock = asyncio.Lock()

    async def register(self, run_id: str) -> None:
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("No active request task is available")
        async with self._lock:
            if run_id in self._tasks:
                raise ValueError(f"Run '{run_id}' is already active")
            self._tasks[run_id] = task

    async def unregister(self, run_id: str) -> None:
        async with self._lock:
            self._tasks.pop(run_id, None)

    async def cancel(self, run_id: str) -> CancelResult:
        async with self._lock:
            task = self._tasks.get(run_id)
            if task is None or task.done():
                return CancelResult(run_id=run_id, cancelled=False)
            task.cancel()
            return CancelResult(run_id=run_id, cancelled=True)

    async def is_active(self, run_id: str) -> bool:
        async with self._lock:
            task = self._tasks.get(run_id)
            return task is not None and not task.done()
