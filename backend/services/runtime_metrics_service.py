from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ModelRunMetric:
    recorded_at: str
    agent_id: str
    stage: str
    provider_id: str
    model: str
    duration_seconds: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    tokens_per_second: float | None
    prompt_tokens_per_second: float | None
    context_window: int
    max_tokens: int
    safe_input_tokens: int
    context_used_tokens: int
    context_remaining_tokens: int
    temperature: float
    assignment_source: str | None


class RuntimeMetricsService:
    """In-memory rolling model metrics suitable for a personal local app."""

    def __init__(self, history_size: int = 100) -> None:
        self._history: deque[ModelRunMetric] = deque(maxlen=history_size)
        self._lock = threading.RLock()

    @staticmethod
    def timer() -> float:
        return time.perf_counter()

    def record(
        self,
        *,
        started_at: float,
        agent_id: str,
        stage: str,
        runtime: dict[str, Any],
        usage: dict[str, Any],
        context_window: int,
        max_tokens: int,
        safe_input_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        duration = max(0.000001, time.perf_counter() - started_at)
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        total_tokens = int(
            usage.get("total_tokens") or input_tokens + output_tokens
        )
        metric = ModelRunMetric(
            recorded_at=datetime.now(timezone.utc).isoformat(),
            agent_id=agent_id,
            stage=stage,
            provider_id=str(runtime.get("provider_id", "")),
            model=str(runtime.get("model", "")),
            duration_seconds=round(duration, 4),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            tokens_per_second=(
                round(output_tokens / duration, 2) if output_tokens else None
            ),
            prompt_tokens_per_second=None,
            context_window=context_window,
            max_tokens=max_tokens,
            safe_input_tokens=safe_input_tokens,
            context_used_tokens=input_tokens,
            context_remaining_tokens=max(0, context_window - input_tokens),
            temperature=temperature,
            assignment_source=runtime.get("assignment_source"),
        )
        with self._lock:
            self._history.appendleft(metric)
        return asdict(metric)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            history = [asdict(item) for item in self._history]
        latest = history[0] if history else None
        return {
            "latest": latest,
            "history": history,
            "summary": self._summary(history),
        }

    @staticmethod
    def _summary(history: list[dict[str, Any]]) -> dict[str, Any]:
        speeds = [
            float(item["tokens_per_second"])
            for item in history
            if item.get("tokens_per_second") is not None
        ]
        durations = [float(item["duration_seconds"]) for item in history]
        return {
            "run_count": len(history),
            "average_tokens_per_second": (
                round(sum(speeds) / len(speeds), 2) if speeds else None
            ),
            "average_duration_seconds": (
                round(sum(durations) / len(durations), 2)
                if durations
                else None
            ),
        }
