from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Dict, Iterable, Iterator, Optional
from uuid import uuid4


class ChangeTransactionRecoveryError(RuntimeError):
    """Raised when an interrupted workspace transaction cannot be restored."""


class ChangeTransactionService:
    """Durable filesystem journal for all-or-nothing change-set application.

    SQLite stores the state machine and manifest. Exact file bytes live in a
    transaction directory next to the database, outside the selected project.
    A process restart restores every transaction left in ``prepared`` or
    ``applying`` before new approvals are accepted.
    """

    _INCOMPLETE_STATES = {"prepared", "applying"}

    def __init__(
        self,
        database_path: Optional[Path],
        *,
        transaction_root: Optional[Path] = None,
    ) -> None:
        self.database_path = database_path.resolve() if database_path else None
        if transaction_root is not None:
            root = transaction_root.resolve()
        elif self.database_path is not None:
            root = self.database_path.parent / "change-transactions"
        else:
            root = Path(tempfile.mkdtemp(prefix="ai-lab-change-transactions-"))
        self.transaction_root = root
        self.transaction_root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._memory: Dict[str, Dict[str, Any]] = {}
        if self.database_path is not None:
            self._initialize_database()

    def prepare(
        self,
        *,
        change_set_id: str,
        workspace: Path,
        proposal_ids: Iterable[str],
        touched_paths: Iterable[Path],
        staged_payloads: Dict[str, str],
    ) -> Dict[str, Any]:
        transaction_id = uuid4().hex
        workspace = workspace.resolve()
        directory = self.transaction_root / transaction_id
        backups = directory / "backups"
        staged = directory / "staged"
        backups.mkdir(parents=True, exist_ok=False)
        staged.mkdir(parents=True, exist_ok=False)

        try:
            snapshots = []
            created_parents: set[str] = set()
            unique_paths = sorted(
                {path.resolve() for path in touched_paths},
                key=lambda item: str(item).casefold(),
            )
            for index, path in enumerate(unique_paths):
                relative = self._relative_to_workspace(path, workspace)
                snapshot = self._snapshot(
                    path=path,
                    relative_path=relative,
                    backup_directory=backups,
                    index=index,
                )
                snapshots.append(snapshot)
                if snapshot["kind"] == "missing":
                    parent = path.parent
                    while parent != workspace and not parent.exists():
                        created_parents.add(
                            parent.relative_to(workspace).as_posix()
                        )
                        parent = parent.parent

            payload_manifest: Dict[str, str] = {}
            for proposal_id, content in staged_payloads.items():
                payload_path = staged / f"{proposal_id}.utf8"
                payload_path.write_bytes(content.encode("utf-8"))
                payload_manifest[proposal_id] = str(
                    payload_path.relative_to(directory)
                )

            now = self._utc_now()
            record = {
                "transaction_id": transaction_id,
                "change_set_id": change_set_id,
                "workspace": str(workspace),
                "state": "prepared",
                "proposal_ids": list(proposal_ids),
                "manifest": {
                    "snapshots": snapshots,
                    "created_parent_dirs": sorted(
                        created_parents,
                        key=lambda item: item.count("/"),
                        reverse=True,
                    ),
                    "staged_payloads": payload_manifest,
                },
                "applied_count": 0,
                "created_at": now,
                "updated_at": now,
                "error": None,
            }
            self._save(record)
            return self._public(record)
        except BaseException:
            shutil.rmtree(directory, ignore_errors=True)
            raise

    def mark_applying(self, transaction_id: str) -> Dict[str, Any]:
        return self._transition(transaction_id, "applying")

    def record_applied(self, transaction_id: str, applied_count: int) -> None:
        with self._lock:
            record = self._get(transaction_id)
            if record["state"] != "applying":
                raise RuntimeError("Only an applying transaction can advance")
            record["applied_count"] = applied_count
            record["updated_at"] = self._utc_now()
            self._save(record)

    def commit(self, transaction_id: str) -> Dict[str, Any]:
        record = self._transition(transaction_id, "committed")
        self._cleanup_files(transaction_id)
        return record

    def rollback(
        self,
        transaction_id: str,
        *,
        error: str = "",
        recovered_after_restart: bool = False,
    ) -> Dict[str, Any]:
        with self._lock:
            record = self._get(transaction_id)
            if record["state"] not in self._INCOMPLETE_STATES:
                return self._public(record)
            try:
                self._restore(record)
            except BaseException as restore_error:
                record["state"] = "recovery_failed"
                record["error"] = str(restore_error)[:2000]
                record["updated_at"] = self._utc_now()
                self._save(record)
                raise ChangeTransactionRecoveryError(
                    f"Could not restore transaction {transaction_id}: "
                    f"{restore_error}"
                ) from restore_error
            record["state"] = (
                "recovered_rollback"
                if recovered_after_restart
                else "rolled_back"
            )
            record["error"] = error[:2000] or None
            record["updated_at"] = self._utc_now()
            self._save(record)
            result = self._public(record)
        self._cleanup_files(transaction_id)
        return result

    def recover_incomplete(
        self,
        on_recovered: Callable[[Dict[str, Any]], None],
    ) -> list[Dict[str, Any]]:
        recovered = []
        for record in self.list_transactions():
            if record["state"] not in self._INCOMPLETE_STATES:
                continue
            rolled_back = self.rollback(
                record["transaction_id"],
                error="Recovered automatically after backend restart.",
                recovered_after_restart=True,
            )
            on_recovered(rolled_back)
            recovered.append(rolled_back)
        return recovered

    def staged_payload_path(
        self,
        transaction_id: str,
        proposal_id: str,
    ) -> Path:
        record = self._get(transaction_id)
        relative = record["manifest"]["staged_payloads"].get(proposal_id)
        if relative is None:
            raise KeyError(f"No staged payload exists for {proposal_id}")
        return self._transaction_directory(transaction_id) / relative

    def list_transactions(
        self,
        *,
        change_set_id: Optional[str] = None,
    ) -> list[Dict[str, Any]]:
        with self._lock:
            if self.database_path is None:
                records = list(self._memory.values())
            else:
                with self._connect() as connection:
                    rows = connection.execute(
                        """
                        SELECT transaction_id, change_set_id, workspace, state,
                               proposal_ids_json, manifest_json, applied_count,
                               created_at, updated_at, error
                        FROM change_transactions
                        ORDER BY created_at DESC
                        """
                    ).fetchall()
                records = [self._from_row(row) for row in rows]
            if change_set_id is not None:
                records = [
                    item
                    for item in records
                    if item["change_set_id"] == change_set_id
                ]
            return [self._public(item) for item in records]

    def _restore(self, record: Dict[str, Any]) -> None:
        workspace = Path(record["workspace"]).resolve()
        directory = self._transaction_directory(record["transaction_id"])
        snapshots = record["manifest"]["snapshots"]
        for snapshot in reversed(snapshots):
            path = (workspace / snapshot["path"]).resolve()
            self._relative_to_workspace(path, workspace)
            if path.exists():
                if path.is_dir():
                    path.rmdir()
                else:
                    path.unlink()
            if snapshot["kind"] == "directory":
                path.mkdir(parents=True, exist_ok=True)
            elif snapshot["kind"] == "file":
                backup = directory / snapshot["backup_path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(backup, path)
            mode = snapshot.get("mode")
            if snapshot["kind"] != "missing" and mode is not None:
                os.chmod(path, int(mode))

        for relative in record["manifest"].get("created_parent_dirs", []):
            parent = (workspace / relative).resolve()
            self._relative_to_workspace(parent, workspace)
            if parent.exists() and parent.is_dir():
                try:
                    parent.rmdir()
                except OSError:
                    pass

    @staticmethod
    def _snapshot(
        *,
        path: Path,
        relative_path: str,
        backup_directory: Path,
        index: int,
    ) -> Dict[str, Any]:
        if not path.exists():
            return {
                "path": relative_path,
                "kind": "missing",
                "mode": None,
                "backup_path": None,
            }
        mode = path.stat().st_mode
        if path.is_dir():
            return {
                "path": relative_path,
                "kind": "directory",
                "mode": mode,
                "backup_path": None,
            }
        backup_name = f"{index:03d}.bin"
        shutil.copyfile(path, backup_directory / backup_name)
        return {
            "path": relative_path,
            "kind": "file",
            "mode": mode,
            "backup_path": f"backups/{backup_name}",
        }

    def _transition(self, transaction_id: str, state: str) -> Dict[str, Any]:
        with self._lock:
            record = self._get(transaction_id)
            record["state"] = state
            record["updated_at"] = self._utc_now()
            self._save(record)
            return self._public(record)

    def _get(self, transaction_id: str) -> Dict[str, Any]:
        if self.database_path is None:
            record = self._memory.get(transaction_id)
        else:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT transaction_id, change_set_id, workspace, state,
                           proposal_ids_json, manifest_json, applied_count,
                           created_at, updated_at, error
                    FROM change_transactions
                    WHERE transaction_id = ?
                    """,
                    (transaction_id,),
                ).fetchone()
            record = self._from_row(row) if row is not None else None
        if record is None:
            raise KeyError(f"Unknown change transaction: {transaction_id}")
        return record

    def _save(self, record: Dict[str, Any]) -> None:
        if self.database_path is None:
            self._memory[record["transaction_id"]] = record
            return
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO change_transactions (
                    transaction_id, change_set_id, workspace, state,
                    proposal_ids_json, manifest_json, applied_count,
                    created_at, updated_at, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(transaction_id) DO UPDATE SET
                    state = excluded.state,
                    proposal_ids_json = excluded.proposal_ids_json,
                    manifest_json = excluded.manifest_json,
                    applied_count = excluded.applied_count,
                    updated_at = excluded.updated_at,
                    error = excluded.error
                """,
                (
                    record["transaction_id"],
                    record["change_set_id"],
                    record["workspace"],
                    record["state"],
                    json.dumps(record["proposal_ids"]),
                    json.dumps(record["manifest"]),
                    record["applied_count"],
                    record["created_at"],
                    record["updated_at"],
                    record["error"],
                ),
            )
            connection.commit()

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS change_transactions (
                    transaction_id TEXT PRIMARY KEY,
                    change_set_id TEXT NOT NULL,
                    workspace TEXT NOT NULL,
                    state TEXT NOT NULL,
                    proposal_ids_json TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    applied_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS change_transactions_change_set
                ON change_transactions (change_set_id)
                """
            )
            connection.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        if self.database_path is None:
            raise RuntimeError("Persistent transaction storage is disabled")
        connection = sqlite3.connect(self.database_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "transaction_id": row["transaction_id"],
            "change_set_id": row["change_set_id"],
            "workspace": row["workspace"],
            "state": row["state"],
            "proposal_ids": json.loads(row["proposal_ids_json"]),
            "manifest": json.loads(row["manifest_json"]),
            "applied_count": row["applied_count"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "error": row["error"],
        }

    @staticmethod
    def _relative_to_workspace(path: Path, workspace: Path) -> str:
        try:
            return path.relative_to(workspace).as_posix()
        except ValueError as error:
            raise PermissionError(
                "Transaction path is outside the selected workspace"
            ) from error

    def _transaction_directory(self, transaction_id: str) -> Path:
        if not transaction_id or any(
            character not in "0123456789abcdef" for character in transaction_id
        ):
            raise ValueError("Invalid transaction id")
        return self.transaction_root / transaction_id

    def _cleanup_files(self, transaction_id: str) -> None:
        shutil.rmtree(
            self._transaction_directory(transaction_id),
            ignore_errors=True,
        )

    @staticmethod
    def _public(record: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(record)
        manifest = result.pop("manifest", {})
        result["touched_paths"] = [
            item["path"] for item in manifest.get("snapshots", [])
        ]
        result["staged_payload_count"] = len(
            manifest.get("staged_payloads", {})
        )
        return result

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
