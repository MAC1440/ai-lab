from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Iterator, List, Optional
from uuid import uuid4


class RepairTaskNotFoundError(LookupError):
    """Raised when a repair task ID does not exist."""


class RepairStore:
    """Persist repair tasks using the Python standard library SQLite client."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def create(self, task: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO repair_tasks (
                    task_id, workspace, title, status, source_run_id,
                    latest_run_id, profile_id, profile_name, display_command,
                    failure_excerpt, created_at, updated_at, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task["task_id"],
                    task["workspace"],
                    task["title"],
                    task["status"],
                    task["source_run_id"],
                    task.get("latest_run_id"),
                    task["profile_id"],
                    task["profile_name"],
                    task["display_command"],
                    task["failure_excerpt"],
                    task["created_at"],
                    task["updated_at"],
                    task.get("resolved_at"),
                ),
            )
            connection.commit()
        return self.get(task["task_id"])

    def get(self, task_id: str) -> Dict[str, Any]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM repair_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            raise RepairTaskNotFoundError(f"Repair task not found: {task_id}")
        return dict(row)

    def find_by_source_run(
        self,
        source_run_id: str,
    ) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM repair_tasks WHERE source_run_id = ?",
                (source_run_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def list(
        self,
        *,
        workspace: Optional[str] = None,
        include_dismissed: bool = False,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        if not isinstance(limit, int) or isinstance(limit, bool):
            raise ValueError("limit must be an integer")
        if limit < 1 or limit > 200:
            raise ValueError("limit must be between 1 and 200")

        clauses: List[str] = []
        parameters: List[Any] = []
        if workspace:
            clauses.append("workspace = ?")
            parameters.append(workspace)
        if not include_dismissed:
            clauses.append("status != 'dismissed'")

        query = "SELECT * FROM repair_tasks"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC LIMIT ?"
        parameters.append(limit)

        with self._lock, self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def update(
        self,
        task_id: str,
        *,
        status: str,
        updated_at: str,
        latest_run_id: Optional[str] = None,
        resolved_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE repair_tasks
                SET status = ?, updated_at = ?,
                    latest_run_id = COALESCE(?, latest_run_id),
                    resolved_at = ?
                WHERE task_id = ?
                """,
                (
                    status,
                    updated_at,
                    latest_run_id,
                    resolved_at,
                    task_id,
                ),
            )
            if cursor.rowcount == 0:
                raise RepairTaskNotFoundError(
                    f"Repair task not found: {task_id}"
                )
            connection.commit()
        return self.get(task_id)

    def add_attempt(
        self,
        task_id: str,
        *,
        kind: str,
        status: str,
        created_at: str,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        attempt_id = uuid4().hex
        with self._lock, self._connect() as connection:
            if connection.execute(
                "SELECT 1 FROM repair_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone() is None:
                raise RepairTaskNotFoundError(
                    f"Repair task not found: {task_id}"
                )
            connection.execute(
                """
                INSERT INTO repair_attempts (
                    attempt_id, task_id, kind, status, run_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (attempt_id, task_id, kind, status, run_id, created_at),
            )
            connection.commit()
        return self.get_attempt(attempt_id)

    def get_attempt(self, attempt_id: str) -> Dict[str, Any]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM repair_attempts WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchone()
        if row is None:
            raise LookupError(f"Repair attempt not found: {attempt_id}")
        return dict(row)

    def list_attempts(self, task_id: str) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM repair_attempts
                WHERE task_id = ?
                ORDER BY created_at ASC, attempt_id ASC
                """,
                (task_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS repair_tasks (
                    task_id TEXT PRIMARY KEY,
                    workspace TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source_run_id TEXT NOT NULL UNIQUE,
                    latest_run_id TEXT,
                    profile_id TEXT NOT NULL,
                    profile_name TEXT NOT NULL,
                    display_command TEXT NOT NULL,
                    failure_excerpt TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    resolved_at TEXT
                );
                CREATE INDEX IF NOT EXISTS repair_tasks_workspace_updated
                ON repair_tasks (workspace, updated_at DESC);
                CREATE TABLE IF NOT EXISTS repair_attempts (
                    attempt_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    run_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES repair_tasks(task_id)
                );
                CREATE INDEX IF NOT EXISTS repair_attempts_task_created
                ON repair_attempts (task_id, created_at ASC);
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
