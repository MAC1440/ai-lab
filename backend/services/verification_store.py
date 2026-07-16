from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Iterator, List, Optional


class VerificationRunNotFoundError(LookupError):
    """Raised when a verification run ID does not exist."""


class VerificationStore:
    """Persist verification summaries using Python's built-in SQLite client."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def create_run(
        self,
        *,
        run_id: str,
        workspace: str,
        profile_id: str,
        profile_name: str,
        project_type: str,
        working_directory: str,
        command: List[str],
        display_command: str,
        proposal_id: Optional[str],
        started_at: str,
    ) -> Dict[str, Any]:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO verification_runs (
                    run_id,
                    workspace,
                    profile_id,
                    profile_name,
                    project_type,
                    working_directory,
                    command_json,
                    display_command,
                    proposal_id,
                    status,
                    started_at,
                    output,
                    output_truncated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', ?, '', 0)
                """,
                (
                    run_id,
                    workspace,
                    profile_id,
                    profile_name,
                    project_type,
                    working_directory,
                    json.dumps(command, ensure_ascii=False),
                    display_command,
                    proposal_id,
                    started_at,
                ),
            )
            connection.commit()

        return self.get_run(run_id)

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        finished_at: str,
        duration_ms: int,
        exit_code: Optional[int],
        output: str,
        output_truncated: bool,
        error: Optional[str],
    ) -> Dict[str, Any]:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE verification_runs
                SET status = ?,
                    finished_at = ?,
                    duration_ms = ?,
                    exit_code = ?,
                    output = ?,
                    output_truncated = ?,
                    error = ?
                WHERE run_id = ?
                """,
                (
                    status,
                    finished_at,
                    duration_ms,
                    exit_code,
                    output,
                    int(output_truncated),
                    error,
                    run_id,
                ),
            )
            if cursor.rowcount == 0:
                raise VerificationRunNotFoundError(
                    f"Verification run not found: {run_id}"
                )
            connection.commit()

        return self.get_run(run_id)

    def get_run(
        self,
        run_id: str,
        *,
        include_output: bool = True,
    ) -> Dict[str, Any]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM verification_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()

        if row is None:
            raise VerificationRunNotFoundError(f"Verification run not found: {run_id}")

        return self._public(row, include_output=include_output)

    def list_runs(
        self,
        *,
        workspace: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        if not isinstance(limit, int) or isinstance(limit, bool):
            raise ValueError("limit must be an integer")
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")

        query = "SELECT * FROM verification_runs"
        parameters: List[Any] = []

        if workspace:
            query += " WHERE workspace = ?"
            parameters.append(workspace)

        query += " ORDER BY started_at DESC LIMIT ?"
        parameters.append(limit)

        with self._lock, self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()

        return [self._public(row, include_output=False) for row in rows]

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS verification_runs (
                    run_id TEXT PRIMARY KEY,
                    workspace TEXT NOT NULL,
                    profile_id TEXT NOT NULL,
                    profile_name TEXT NOT NULL,
                    project_type TEXT NOT NULL,
                    working_directory TEXT NOT NULL,
                    command_json TEXT NOT NULL,
                    display_command TEXT NOT NULL,
                    proposal_id TEXT,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    duration_ms INTEGER,
                    exit_code INTEGER,
                    output TEXT NOT NULL DEFAULT '',
                    output_truncated INTEGER NOT NULL DEFAULT 0,
                    error TEXT
                );

                CREATE INDEX IF NOT EXISTS
                    verification_runs_workspace_started
                ON verification_runs (workspace, started_at DESC);
                """
            )
            connection.execute(
                """
                UPDATE verification_runs
                SET status = 'error',
                    finished_at = COALESCE(finished_at, started_at),
                    error = COALESCE(
                        error,
                        'The backend stopped before this run completed.'
                    )
                WHERE status = 'running'
                """
            )
            connection.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(
            self.database_path,
            timeout=10,
        )
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _public(
        row: sqlite3.Row,
        *,
        include_output: bool,
    ) -> Dict[str, Any]:
        output = str(row["output"] or "")
        result: Dict[str, Any] = {
            "run_id": row["run_id"],
            "workspace": row["workspace"],
            "profile_id": row["profile_id"],
            "profile_name": row["profile_name"],
            "project_type": row["project_type"],
            "working_directory": row["working_directory"],
            "command": json.loads(row["command_json"]),
            "display_command": row["display_command"],
            "proposal_id": row["proposal_id"],
            "status": row["status"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "duration_ms": row["duration_ms"],
            "exit_code": row["exit_code"],
            "output_excerpt": output[-4000:],
            "output_truncated": bool(row["output_truncated"]),
            "error": row["error"],
        }

        if include_output:
            result["output"] = output

        return result
