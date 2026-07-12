from __future__ import annotations

import hashlib
import os
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import unified_diff
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Optional
from uuid import uuid4

from services.workspace_service import WorkspaceService


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
    status: str
    operation: str
    diff: str
    created_at: str
    resolved_at: Optional[str]
    base_exists: bool
    base_sha256: str
    proposed_content: str


class ChangeService:
    """Create reviewable file changes and apply them only after approval.

    Proposals are intentionally held in memory for the first implementation.
    A backend restart therefore clears pending proposals.
    """

    def __init__(
        self,
        workspace_service: WorkspaceService,
        *,
        max_file_bytes: int = 1_000_000,
    ) -> None:
        if max_file_bytes < 1:
            raise ValueError("max_file_bytes must be positive")

        self.workspace_service = workspace_service
        self.max_file_bytes = max_file_bytes
        self._proposals: Dict[str, _StoredProposal] = {}
        self._lock = RLock()

    def propose(
        self,
        *,
        file_path: str,
        content: str,
        summary: str = "",
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
        if before_content == content and base_exists:
            raise ValueError("The proposed content is identical to the file")

        operation = "update" if base_exists else "create"
        relative_path = str(target.relative_to(workspace_root))
        diff = self._build_diff(
            file_path=relative_path,
            before_content=before_content,
            after_content=content,
            base_exists=base_exists,
        )
        now = self._utc_now()
        proposal = _StoredProposal(
            proposal_id=uuid4().hex,
            workspace=str(workspace_root),
            file_path=relative_path,
            summary=summary.strip(),
            status="pending",
            operation=operation,
            diff=diff,
            created_at=now,
            resolved_at=None,
            base_exists=base_exists,
            base_sha256=self._hash_text(before_content),
            proposed_content=content,
        )

        with self._lock:
            self._proposals[proposal.proposal_id] = proposal

        return self._public(proposal)

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
                    "The active workspace changed after this proposal was created"
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
                    "Ask the agent to inspect it again and create a new proposal."
                )

            self._atomic_write(target, proposal.proposed_content)
            proposal.status = "approved"
            proposal.resolved_at = self._utc_now()
            return self._public(proposal)

    def reject(self, proposal_id: str) -> Dict[str, Any]:
        with self._lock:
            proposal = self._get_stored(proposal_id)
            self._require_pending(proposal)
            proposal.status = "rejected"
            proposal.resolved_at = self._utc_now()
            return self._public(proposal)

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
                f"File exceeds the {self.max_file_bytes}-byte proposal limit: "
                f"{display_path}"
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
            }
        )
