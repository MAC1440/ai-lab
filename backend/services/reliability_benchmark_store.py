from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any


class ReliabilityBenchmarkRunNotFoundError(LookupError):
    """Raised when a reliability benchmark run does not exist."""


class ReliabilityBenchmarkStore:
    """Persist benchmark runs and scenario evidence in SQLite."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def create_run(self, run: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO reliability_benchmark_runs (
                    run_id, suite, agent_override, repetitions, status,
                    started_at, finished_at, duration_ms, scenario_count,
                    passed_count, failed_count, pass_rate, error
                ) VALUES (?, ?, ?, ?, 'running', ?, NULL, NULL, ?, 0, 0, 0, NULL)
                """,
                (
                    run["run_id"],
                    run["suite"],
                    run.get("agent_override"),
                    run["repetitions"],
                    run["started_at"],
                    run["scenario_count"],
                ),
            )
            connection.commit()
        return self.get_run(str(run["run_id"]))

    def add_result(
        self,
        run_id: str,
        *,
        sequence: int,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO reliability_benchmark_results (
                    run_id, sequence, scenario_id, repetition, category,
                    project_type, agent_id, status, duration_ms, score,
                    assertions_json, metrics_json, error, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    sequence,
                    result["scenario_id"],
                    result["repetition"],
                    result["category"],
                    result["project_type"],
                    result.get("agent_id"),
                    result["status"],
                    result["duration_ms"],
                    result["score"],
                    json.dumps(
                        result.get("assertions", []),
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        result.get("metrics", {}),
                        ensure_ascii=False,
                    ),
                    result.get("error"),
                    result["created_at"],
                ),
            )
            connection.commit()
        return result

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        finished_at: str,
        duration_ms: int,
        passed_count: int,
        failed_count: int,
        pass_rate: float,
        error: str | None = None,
    ) -> dict[str, Any]:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE reliability_benchmark_runs
                SET status = ?,
                    finished_at = ?,
                    duration_ms = ?,
                    passed_count = ?,
                    failed_count = ?,
                    pass_rate = ?,
                    error = ?
                WHERE run_id = ?
                """,
                (
                    status,
                    finished_at,
                    duration_ms,
                    passed_count,
                    failed_count,
                    pass_rate,
                    error,
                    run_id,
                ),
            )
            if cursor.rowcount == 0:
                raise ReliabilityBenchmarkRunNotFoundError(
                    f"Reliability benchmark run not found: {run_id}"
                )
            connection.commit()
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> dict[str, Any]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM reliability_benchmark_runs
                WHERE run_id = ?
                """,
                (self._required_id(run_id),),
            ).fetchone()
            if row is None:
                raise ReliabilityBenchmarkRunNotFoundError(
                    f"Reliability benchmark run not found: {run_id}"
                )
            result_rows = connection.execute(
                """
                SELECT *
                FROM reliability_benchmark_results
                WHERE run_id = ?
                ORDER BY sequence ASC
                """,
                (run_id,),
            ).fetchall()
        result = self._public_run(row)
        result["results"] = [
            self._public_result(item) for item in result_rows
        ]
        return result

    def list_runs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        if not isinstance(limit, int) or isinstance(limit, bool):
            raise TypeError("limit must be an integer")
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM reliability_benchmark_runs
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._public_run(row) for row in rows]

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS reliability_benchmark_runs (
                    run_id TEXT PRIMARY KEY,
                    suite TEXT NOT NULL,
                    agent_override TEXT,
                    repetitions INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    duration_ms INTEGER,
                    scenario_count INTEGER NOT NULL,
                    passed_count INTEGER NOT NULL DEFAULT 0,
                    failed_count INTEGER NOT NULL DEFAULT 0,
                    pass_rate REAL NOT NULL DEFAULT 0,
                    error TEXT
                );

                CREATE TABLE IF NOT EXISTS reliability_benchmark_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    scenario_id TEXT NOT NULL,
                    repetition INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    project_type TEXT NOT NULL,
                    agent_id TEXT,
                    status TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    score REAL NOT NULL,
                    assertions_json TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(run_id, sequence),
                    FOREIGN KEY(run_id)
                        REFERENCES reliability_benchmark_runs(run_id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS reliability_runs_started
                ON reliability_benchmark_runs(started_at DESC);

                CREATE INDEX IF NOT EXISTS reliability_results_run
                ON reliability_benchmark_results(run_id, sequence);
                """
            )
            connection.execute(
                """
                UPDATE reliability_benchmark_runs
                SET status = 'interrupted',
                    finished_at = COALESCE(finished_at, ?),
                    error = COALESCE(
                        error,
                        'The backend stopped before this benchmark completed.'
                    )
                WHERE status = 'running'
                """,
                (self._utc_now(),),
            )
            connection.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _public_run(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "run_id": row["run_id"],
            "suite": row["suite"],
            "agent_override": row["agent_override"],
            "repetitions": row["repetitions"],
            "status": row["status"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "duration_ms": row["duration_ms"],
            "scenario_count": row["scenario_count"],
            "passed_count": row["passed_count"],
            "failed_count": row["failed_count"],
            "pass_rate": row["pass_rate"],
            "error": row["error"],
        }

    @staticmethod
    def _public_result(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "sequence": row["sequence"],
            "scenario_id": row["scenario_id"],
            "repetition": row["repetition"],
            "category": row["category"],
            "project_type": row["project_type"],
            "agent_id": row["agent_id"],
            "status": row["status"],
            "duration_ms": row["duration_ms"],
            "score": row["score"],
            "assertions": json.loads(row["assertions_json"]),
            "metrics": json.loads(row["metrics_json"]),
            "error": row["error"],
            "created_at": row["created_at"],
        }

    @staticmethod
    def _required_id(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("run_id must be a non-empty string")
        return value.strip()

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
