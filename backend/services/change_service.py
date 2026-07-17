from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import unified_diff
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4
from contextlib import closing

from services.workspace_service import WorkspaceService


ChangeProposalStatus = Literal["pending", "approved", "rejected"]
_VALID_STATUSES = {"pending", "approved", "rejected"}


class ChangeProposalNotFoundError(LookupError):
    """Raised when a proposal ID does not exist."""


class ChangeProposalStateError(RuntimeError):
    """Raised when a proposal has already been resolved."""


class ChangeProposalConflictError(RuntimeError):
    """Raised when the workspace or source file changed after proposal time."""


@dataclass
class _StoredProposal:
    proposal_id: str
    workspace: str
    file_path: str
    summary: str
    status: ChangeProposalStatus
    operation: Literal["create", "update"]
    diff: str
    created_at: str
    resolved_at: Optional[str]
    base_exists: bool
    base_sha256: str
    proposed_content: str
    change_set_id: Optional[str]
    repair_task_id: Optional[str]


class ChangeService:
    """Create reviewable file changes and apply them only after approval.

    Proposals can be persisted to SQLite so review state survives backend
    restarts. Tests and small embedded uses may omit ``database_path`` to keep
    the original in-memory behaviour.
    """

    def __init__(
        self,
        workspace_service: WorkspaceService,
        *,
        max_file_bytes: int = 1_000_000,
        database_path: Optional[Path] = None,
    ) -> None:
        if max_file_bytes < 1:
            raise ValueError("max_file_bytes must be positive")

        self.workspace_service = workspace_service
        self.max_file_bytes = max_file_bytes
        self._proposals: Dict[str, _StoredProposal] = {}
        self._lock = RLock()
        self.database_path = database_path.resolve() if database_path else None
        if self.database_path is not None:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize_database()
            self._load_proposals()

    def propose(
        self,
        *,
        file_path: str,
        content: str,
        summary: str = "",
        change_set_id: Optional[str] = None,
        repair_task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        clean_path = self._validate_path(file_path)

        if not isinstance(content, str):
            raise ValueError("content must be a string")
        if len(content.encode("utf-8")) > self.max_file_bytes:
            raise ValueError(
                f"Proposed content exceeds {self.max_file_bytes} bytes"
            )
        if not isinstance(summary, str):
            raise ValueError("summary must be a string")

        workspace_root = self.workspace_service.get_workspace()
        target = self.workspace_service.resolve_workspace_path(clean_path)

        if target.exists() and target.is_dir():
            raise IsADirectoryError(
                f"Cannot propose text content for a folder: {clean_path}"
            )

        base_exists = target.exists()
        before_content = self._read_current_content(target, clean_path)

        if base_exists and before_content == content:
            raise ValueError("The proposed content is identical to the file")

        operation: Literal["create", "update"] = (
            "update" if base_exists else "create"
        )
        relative_path = str(target.relative_to(workspace_root))
        diff = self._build_diff(
            file_path=relative_path,
            before_content=before_content,
            after_content=content,
            base_exists=base_exists,
        )

        proposal = _StoredProposal(
            proposal_id=uuid4().hex,
            workspace=str(workspace_root.resolve()),
            file_path=relative_path,
            summary=summary.strip(),
            status="pending",
            operation=operation,
            diff=diff,
            created_at=self._utc_now(),
            resolved_at=None,
            base_exists=base_exists,
            base_sha256=self._hash_text(before_content),
            proposed_content=content,
            change_set_id=self._optional_id(change_set_id, "change_set_id"),
            repair_task_id=self._optional_id(repair_task_id, "repair_task_id"),
        )

        with self._lock:
            self._proposals[proposal.proposal_id] = proposal
            self._save(proposal)

        return self._public(proposal)

    def list_proposals(
        self,
        *,
        status: Optional[ChangeProposalStatus] = None,
        change_set_id: Optional[str] = None,
        repair_task_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if status is not None and status not in _VALID_STATUSES:
            raise ValueError(
                "status must be one of: pending, approved, rejected"
            )

        with self._lock:
            proposals = [
                proposal
                for proposal in self._proposals.values()
                if status is None or proposal.status == status
                if change_set_id is None
                or proposal.change_set_id == change_set_id
                if repair_task_id is None
                or proposal.repair_task_id == repair_task_id
            ]
            proposals.sort(
                key=lambda proposal: proposal.created_at,
                reverse=True,
            )
            return [self._public(proposal) for proposal in proposals]

    def get(self, proposal_id: str) -> Dict[str, Any]:
        with self._lock:
            proposal = self._get_stored(proposal_id)
            return self._public(proposal)

    def approve(self, proposal_id: str) -> Dict[str, Any]:
        with self._lock:
            proposal = self._get_stored(proposal_id)
            self._require_pending(proposal)

            active_workspace = self.workspace_service.get_workspace()
            active_workspace_text = os.path.normcase(
                str(active_workspace.resolve())
            )
            proposal_workspace_text = os.path.normcase(proposal.workspace)

            if active_workspace_text != proposal_workspace_text:
                raise ChangeProposalConflictError(
                    "The active workspace changed after this proposal was "
                    "created"
                )

            target = self.workspace_service.resolve_workspace_path(
                proposal.file_path
            )
            current_exists = target.exists()

            if current_exists and target.is_dir():
                raise ChangeProposalConflictError(
                    "The proposed file path now points to a folder"
                )

            current_content = self._read_current_content(
                target,
                proposal.file_path,
            )
            current_hash = self._hash_text(current_content)

            if (
                current_exists != proposal.base_exists
                or current_hash != proposal.base_sha256
            ):
                raise ChangeProposalConflictError(
                    "The file changed after this proposal was created. "
                    "Ask the agent to inspect it again and create a new "
                    "proposal."
                )

            self._atomic_write(target, proposal.proposed_content)
            proposal.status = "approved"
            proposal.resolved_at = self._utc_now()
            self._save(proposal)
            return self._public(proposal)

    def reject(self, proposal_id: str) -> Dict[str, Any]:
        with self._lock:
            proposal = self._get_stored(proposal_id)
            self._require_pending(proposal)
            proposal.status = "rejected"
            proposal.resolved_at = self._utc_now()
            self._save(proposal)
            return self._public(proposal)

    def approve_change_set(self, change_set_id: str) -> List[Dict[str, Any]]:
        """Approve every pending proposal in a model turn.

        Each proposal still performs the normal workspace and stale-file
        checks. The method stops on the first conflict so an unsafe proposal is
        never silently skipped.
        """

        clean_id = self._required_id(change_set_id, "change_set_id")
        proposals = self.list_proposals(
            status="pending",
            change_set_id=clean_id,
        )
        if not proposals:
            raise ChangeProposalNotFoundError(
                f"No pending proposals found for change set: {clean_id}"
            )
        return [self.approve(item["proposal_id"]) for item in proposals]

    def reject_change_set(self, change_set_id: str) -> List[Dict[str, Any]]:
        clean_id = self._required_id(change_set_id, "change_set_id")
        proposals = self.list_proposals(
            status="pending",
            change_set_id=clean_id,
        )
        if not proposals:
            raise ChangeProposalNotFoundError(
                f"No pending proposals found for change set: {clean_id}"
            )
        return [self.reject(item["proposal_id"]) for item in proposals]

    def _get_stored(self, proposal_id: str) -> _StoredProposal:
        if not isinstance(proposal_id, str) or not proposal_id.strip():
            raise ValueError("proposal_id must be a non-empty string")

        proposal = self._proposals.get(proposal_id.strip())
        if proposal is None:
            raise ChangeProposalNotFoundError(
                f"Change proposal not found: {proposal_id}"
            )
        return proposal

    @staticmethod
    def _require_pending(proposal: _StoredProposal) -> None:
        if proposal.status != "pending":
            raise ChangeProposalStateError(
                f"Proposal is already {proposal.status}"
            )

    def _read_current_content(self, target: Path, display_path: str) -> str:
        if not target.exists():
            return ""

        if target.stat().st_size > self.max_file_bytes:
            raise ValueError(
                f"File exceeds the {self.max_file_bytes}-byte proposal "
                f"limit: {display_path}"
            )

        try:
            return target.read_bytes().decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(
                f"File is not readable UTF-8 text: {display_path}"
            ) from error

    @staticmethod
    def _build_diff(
        *,
        file_path: str,
        before_content: str,
        after_content: str,
        base_exists: bool,
    ) -> str:
        before_name = f"a/{file_path}" if base_exists else "/dev/null"
        after_name = f"b/{file_path}"

        return "".join(
            unified_diff(
                before_content.splitlines(keepends=True),
                after_content.splitlines(keepends=True),
                fromfile=before_name,
                tofile=after_name,
                lineterm="\n",
            )
        )

    @staticmethod
    def _atomic_write(target: Path, content: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        existing_mode = target.stat().st_mode if target.exists() else None
        temp_path: Optional[str] = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_file.write(content)
                temp_file.flush()
                os.fsync(temp_file.fileno())
                temp_path = temp_file.name

            if existing_mode is not None:
                os.chmod(temp_path, existing_mode)

            os.replace(temp_path, target)
            temp_path = None
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    @staticmethod
    def _hash_text(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_path(file_path: str) -> str:
        if not isinstance(file_path, str) or not file_path.strip():
            raise ValueError("file_path must be a non-empty string")
        return file_path.strip()

    @staticmethod
    def _required_id(value: str, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string")
        return value.strip()

    @classmethod
    def _optional_id(
        cls,
        value: Optional[str],
        field_name: str,
    ) -> Optional[str]:
        if value is None:
            return None
        return cls._required_id(value, field_name)

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _public(proposal: _StoredProposal) -> Dict[str, Any]:
        return deepcopy(
            {
                "proposal_id": proposal.proposal_id,
                "workspace": proposal.workspace,
                "file_path": proposal.file_path,
                "summary": proposal.summary,
                "status": proposal.status,
                "operation": proposal.operation,
                "diff": proposal.diff,
                "created_at": proposal.created_at,
                "resolved_at": proposal.resolved_at,
                "change_set_id": proposal.change_set_id,
                "repair_task_id": proposal.repair_task_id,
            }
        )

    def _connect(self) -> sqlite3.Connection:
        if self.database_path is None:
            raise RuntimeError("Change persistence is not configured")
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS change_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    workspace TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    status TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    diff TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    base_exists INTEGER NOT NULL,
                    base_sha256 TEXT NOT NULL,
                    proposed_content TEXT NOT NULL,
                    change_set_id TEXT,
                    repair_task_id TEXT
                );
                CREATE INDEX IF NOT EXISTS change_proposals_workspace_created
                ON change_proposals (workspace, created_at DESC);
                CREATE INDEX IF NOT EXISTS change_proposals_change_set
                ON change_proposals (change_set_id);
                CREATE INDEX IF NOT EXISTS change_proposals_repair_task
                ON change_proposals (repair_task_id);
                """
            )

    def _load_proposals(self) -> None:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM change_proposals"
            ).fetchall()
        with self._lock:
            for row in rows:
                proposal = _StoredProposal(
                    proposal_id=row["proposal_id"],
                    workspace=row["workspace"],
                    file_path=row["file_path"],
                    summary=row["summary"],
                    status=row["status"],
                    operation=row["operation"],
                    diff=row["diff"],
                    created_at=row["created_at"],
                    resolved_at=row["resolved_at"],
                    base_exists=bool(row["base_exists"]),
                    base_sha256=row["base_sha256"],
                    proposed_content=row["proposed_content"],
                    change_set_id=row["change_set_id"],
                    repair_task_id=row["repair_task_id"],
                )
                self._proposals[proposal.proposal_id] = proposal

    def _save(self, proposal: _StoredProposal) -> None:
        if self.database_path is None:
            return
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO change_proposals (
                    proposal_id, workspace, file_path, summary, status,
                    operation, diff, created_at, resolved_at, base_exists,
                    base_sha256, proposed_content, change_set_id,
                    repair_task_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(proposal_id) DO UPDATE SET
                    status = excluded.status,
                    resolved_at = excluded.resolved_at,
                    proposed_content = excluded.proposed_content,
                    change_set_id = excluded.change_set_id,
                    repair_task_id = excluded.repair_task_id
                """,
                (
                    proposal.proposal_id,
                    proposal.workspace,
                    proposal.file_path,
                    proposal.summary,
                    proposal.status,
                    proposal.operation,
                    proposal.diff,
                    proposal.created_at,
                    proposal.resolved_at,
                    int(proposal.base_exists),
                    proposal.base_sha256,
                    proposal.proposed_content,
                    proposal.change_set_id,
                    proposal.repair_task_id,
                ),
            )
            connection.commit()
