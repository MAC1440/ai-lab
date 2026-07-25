from __future__ import annotations

import sqlite3
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


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
    """
    Store bounded model-run telemetry.

    When ``database_path`` is supplied, metrics survive backend restarts.
    The in-memory mode remains available for isolated tests and lightweight
    callers that do not need persistence.
    """

    def __init__(
        self,
        database_path: Path | str | None = None,
        history_size: int = 100,
    ) -> None:
        if history_size < 1:
            raise ValueError("history_size must be at least 1")

        self.history_size = history_size
        self.database_path = (
            Path(database_path).expanduser().resolve()
            if database_path is not None
            else None
        )
        self._history: deque[ModelRunMetric] = deque(maxlen=history_size)
        self._lock = threading.RLock()

        if self.database_path is not None:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize_database()

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
            assignment_source=(
                str(runtime["assignment_source"])
                if runtime.get("assignment_source") is not None
                else None
            ),
        )

        with self._lock:
            if self.database_path is None:
                self._history.appendleft(metric)
            else:
                self._insert(metric)
                self._trim_history()

        return asdict(metric)

    def snapshot(
        self,
        *,
        limit: int | None = None,
        stage: str | None = None,
        agent_id: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        resolved_limit = min(
            max(1, limit or self.history_size),
            self.history_size,
        )

        with self._lock:
            if self.database_path is None:
                history = [
                    asdict(item)
                    for item in self._history
                    if self._matches(
                        item,
                        stage=stage,
                        agent_id=agent_id,
                        model=model,
                    )
                ][:resolved_limit]
            else:
                history = self._read_history(
                    limit=resolved_limit,
                    stage=stage,
                    agent_id=agent_id,
                    model=model,
                )

        latest = history[0] if history else None
        return {
            "latest": latest,
            "history": history,
            "summary": self._summary(history),
            "filters": {
                "limit": resolved_limit,
                "stage": stage,
                "agent_id": agent_id,
                "model": model,
            },
            "persistent": self.database_path is not None,
        }

    def clear(self) -> int:
        """Delete all stored metrics and return the removed row count."""
        with self._lock:
            if self.database_path is None:
                count = len(self._history)
                self._history.clear()
                return count

            with self._connect() as connection:
                result = connection.execute("DELETE FROM runtime_metrics")
                connection.commit()
                return max(0, int(result.rowcount or 0))

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recorded_at TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    duration_seconds REAL NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    tokens_per_second REAL,
                    prompt_tokens_per_second REAL,
                    context_window INTEGER NOT NULL,
                    max_tokens INTEGER NOT NULL,
                    safe_input_tokens INTEGER NOT NULL,
                    context_used_tokens INTEGER NOT NULL,
                    context_remaining_tokens INTEGER NOT NULL,
                    temperature REAL NOT NULL,
                    assignment_source TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_runtime_metrics_recorded_at
                ON runtime_metrics(recorded_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_runtime_metrics_stage
                ON runtime_metrics(stage)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_runtime_metrics_agent
                ON runtime_metrics(agent_id)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_runtime_metrics_model
                ON runtime_metrics(model)
                """
            )
            connection.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """
        Open and reliably close a SQLite connection.

        sqlite3.Connection's own context manager only manages transactions.
        It does not close the connection when the ``with`` block exits. That
        leaves the database file locked on Windows and prevents temporary test
        directories from being removed.
        """
        if self.database_path is None:
            raise RuntimeError("Persistent runtime metrics are not configured")

        connection = sqlite3.connect(
            self.database_path,
            timeout=10,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row

        try:
            yield connection
        finally:
            connection.close()

    def _insert(self, metric: ModelRunMetric) -> None:
        values = asdict(metric)
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)

        with self._connect() as connection:
            connection.execute(
                f"""
                INSERT INTO runtime_metrics ({columns})
                VALUES ({placeholders})
                """,
                tuple(values.values()),
            )
            connection.commit()

    def _trim_history(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM runtime_metrics
                WHERE id NOT IN (
                    SELECT id
                    FROM runtime_metrics
                    ORDER BY id DESC
                    LIMIT ?
                )
                """,
                (self.history_size,),
            )
            connection.commit()

    def _read_history(
        self,
        *,
        limit: int,
        stage: str | None,
        agent_id: str | None,
        model: str | None,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        values: list[Any] = []

        for column, value in (
            ("stage", stage),
            ("agent_id", agent_id),
            ("model", model),
        ):
            if value:
                where.append(f"{column} = ?")
                values.append(value)

        where_clause = f"WHERE {' AND '.join(where)}" if where else ""
        values.append(limit)

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    recorded_at,
                    agent_id,
                    stage,
                    provider_id,
                    model,
                    duration_seconds,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    tokens_per_second,
                    prompt_tokens_per_second,
                    context_window,
                    max_tokens,
                    safe_input_tokens,
                    context_used_tokens,
                    context_remaining_tokens,
                    temperature,
                    assignment_source
                FROM runtime_metrics
                {where_clause}
                ORDER BY id DESC
                LIMIT ?
                """,
                tuple(values),
            ).fetchall()

        return [dict(row) for row in rows]

    @staticmethod
    def _matches(
        metric: ModelRunMetric,
        *,
        stage: str | None,
        agent_id: str | None,
        model: str | None,
    ) -> bool:
        return (
            (stage is None or metric.stage == stage)
            and (agent_id is None or metric.agent_id == agent_id)
            and (model is None or metric.model == model)
        )

    @staticmethod
    def _summary(history: list[dict[str, Any]]) -> dict[str, Any]:
        speeds = [
            float(item["tokens_per_second"])
            for item in history
            if item.get("tokens_per_second") is not None
        ]
        durations = [float(item["duration_seconds"]) for item in history]
        input_tokens = [int(item["input_tokens"]) for item in history]
        output_tokens = [int(item["output_tokens"]) for item in history]

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
            "total_input_tokens": sum(input_tokens),
            "total_output_tokens": sum(output_tokens),
        }