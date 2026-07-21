from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Iterator, List, Optional
from uuid import uuid4


class ProjectTaskNotFoundError(LookupError):
    """Raised when a persisted project task does not exist."""


class ProjectTaskStore:
    """Persist durable project-task state and its audit trail in SQLite."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def create(self, task: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO project_tasks (
                    task_id, workspace, title, goal, agent_id, status, phase,
                    verification_profile_id, current_change_set_id,
                    current_agent_run_id, latest_verification_run_id,
                    repair_task_id, attempt_count, max_attempts, last_error,
                    created_at, updated_at, completed_at, cancelled_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task["task_id"],
                    task["workspace"],
                    task["title"],
                    task["goal"],
                    task["agent_id"],
                    task["status"],
                    task["phase"],
                    task.get("verification_profile_id"),
                    task.get("current_change_set_id"),
                    task.get("current_agent_run_id"),
                    task.get("latest_verification_run_id"),
                    task.get("repair_task_id"),
                    task.get("attempt_count", 0),
                    task.get("max_attempts", 3),
                    task.get("last_error"),
                    task["created_at"],
                    task["updated_at"],
                    task.get("completed_at"),
                    task.get("cancelled_at"),
                ),
            )
            connection.commit()
        return self.get(task["task_id"])

    def get(self, task_id: str) -> Dict[str, Any]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM project_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            raise ProjectTaskNotFoundError(f"Project task not found: {task_id}")
        return dict(row)

    def list(self, *, workspace: str, limit: int = 50) -> List[Dict[str, Any]]:
        if not isinstance(limit, int) or isinstance(limit, bool):
            raise ValueError("limit must be an integer")
        if limit < 1 or limit > 200:
            raise ValueError("limit must be between 1 and 200")
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM project_tasks
                WHERE workspace = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (workspace, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def update(self, task_id: str, **values: Any) -> Dict[str, Any]:
        allowed = {
            "status",
            "phase",
            "verification_profile_id",
            "current_change_set_id",
            "current_agent_run_id",
            "latest_verification_run_id",
            "repair_task_id",
            "attempt_count",
            "last_error",
            "updated_at",
            "completed_at",
            "cancelled_at",
        }
        invalid = set(values) - allowed
        if invalid:
            raise ValueError(f"Unsupported project task fields: {sorted(invalid)}")
        if not values:
            return self.get(task_id)

        assignments = ", ".join(f"{column} = ?" for column in values)
        parameters = [*values.values(), task_id]
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE project_tasks SET {assignments} WHERE task_id = ?",  # noqa: S608
                parameters,
            )
            if cursor.rowcount == 0:
                raise ProjectTaskNotFoundError(
                    f"Project task not found: {task_id}"
                )
            connection.commit()
        return self.get(task_id)

    def add_event(
        self,
        task_id: str,
        *,
        event_type: str,
        message: str,
        payload: Optional[Dict[str, Any]],
        created_at: str,
    ) -> Dict[str, Any]:
        event_id = uuid4().hex
        with self._lock, self._connect() as connection:
            if connection.execute(
                "SELECT 1 FROM project_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone() is None:
                raise ProjectTaskNotFoundError(
                    f"Project task not found: {task_id}"
                )
            connection.execute(
                """
                INSERT INTO project_task_events (
                    event_id, task_id, event_type, message, payload_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    task_id,
                    event_type,
                    message,
                    json.dumps(payload or {}, ensure_ascii=False),
                    created_at,
                ),
            )
            connection.commit()
        return {
            "event_id": event_id,
            "task_id": task_id,
            "event_type": event_type,
            "message": message,
            "payload": payload or {},
            "created_at": created_at,
        }

    def list_events(self, task_id: str) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM project_task_events
                WHERE task_id = ?
                ORDER BY created_at ASC, event_id ASC
                """,
                (task_id,),
            ).fetchall()
        events: List[Dict[str, Any]] = []
        for row in rows:
            event = dict(row)
            event["payload"] = json.loads(event.pop("payload_json") or "{}")
            events.append(event)
        return events

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS project_tasks (
                    task_id TEXT PRIMARY KEY,
                    workspace TEXT NOT NULL,
                    title TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    verification_profile_id TEXT,
                    current_change_set_id TEXT,
                    current_agent_run_id TEXT,
                    latest_verification_run_id TEXT,
                    repair_task_id TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    cancelled_at TEXT
                );
                CREATE INDEX IF NOT EXISTS project_tasks_workspace_updated
                ON project_tasks (workspace, updated_at DESC);

                CREATE TABLE IF NOT EXISTS project_task_events (
                    event_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES project_tasks(task_id)
                );
                CREATE INDEX IF NOT EXISTS project_task_events_task_created
                ON project_task_events (task_id, created_at ASC);
                """
            )
            connection.execute(
                """
                UPDATE project_tasks
                SET status = 'paused',
                    phase = 'interrupted',
                    current_agent_run_id = NULL,
                    updated_at = COALESCE(updated_at, created_at),
                    last_error = COALESCE(
                        last_error,
                        'The backend stopped while this task was active.'
                    )
                WHERE status IN ('running', 'verifying')
                """
            )
            connection.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()
