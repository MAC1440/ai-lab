from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

from services.change_service import ChangeService
from services.repair_store import RepairStore, RepairTaskNotFoundError
from services.verification_store import VerificationStore
from services.workspace_service import WorkspaceService


REPAIRABLE_RUN_STATUSES = {"failed", "error", "timed_out"}
TERMINAL_TASK_STATUSES = {"passed", "dismissed"}
MAX_FAILURE_EXCERPT_CHARS = 20_000
MAX_AGENT_ATTEMPTS = 3


class RepairTaskStateError(RuntimeError):
    """Raised when a repair task cannot perform the requested transition."""


class RepairService:
    """Connect failed checks, proposed changes and follow-up verification."""

    def __init__(
        self,
        *,
        workspace_service: WorkspaceService,
        verification_store: VerificationStore,
        change_service: ChangeService,
        store: RepairStore,
    ) -> None:
        self.workspace_service = workspace_service
        self.verification_store = verification_store
        self.change_service = change_service
        self.store = store

    def create_from_verification(self, run_id: str) -> Dict[str, Any]:
        clean_id = self._required_id(run_id, "run_id")
        existing = self.store.find_by_source_run(clean_id)
        if existing is not None:
            return self._enrich(existing)

        run = self.verification_store.get_run(clean_id)
        self._require_active_workspace(run["workspace"])
        if run["status"] not in REPAIRABLE_RUN_STATUSES:
            raise RepairTaskStateError(
                "Only failed, errored, or timed-out verification runs can "
                "become repair tasks"
            )

        now = self._utc_now()
        raw_output = (run.get("output") or run.get("output_excerpt") or "").strip()
        error = (run.get("error") or "").strip()
        excerpt = "\n\n".join(part for part in (raw_output, error) if part)
        excerpt = excerpt[-MAX_FAILURE_EXCERPT_CHARS:]

        task = self.store.create(
            {
                "task_id": uuid4().hex,
                "workspace": run["workspace"],
                "title": f"Repair {run['profile_name']}",
                "status": "open",
                "source_run_id": clean_id,
                "latest_run_id": clean_id,
                "profile_id": run["profile_id"],
                "profile_name": run["profile_name"],
                "display_command": run["display_command"],
                "failure_excerpt": excerpt or "No verification output was captured.",
                "created_at": now,
                "updated_at": now,
                "resolved_at": None,
            }
        )
        return self._enrich(task)

    def list_tasks(
        self,
        *,
        include_dismissed: bool = False,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        workspace = str(self.workspace_service.get_workspace().resolve())
        return [
            self._enrich(task)
            for task in self.store.list(
                workspace=workspace,
                include_dismissed=include_dismissed,
                limit=limit,
            )
        ]

    def get_task(self, task_id: str) -> Dict[str, Any]:
        task = self.store.get(self._required_id(task_id, "task_id"))
        self._require_active_workspace(task["workspace"])
        return self._enrich(task)

    def dismiss(self, task_id: str) -> Dict[str, Any]:
        task = self.get_task(task_id)
        if task["status"] == "passed":
            raise RepairTaskStateError("A passed repair task is already resolved")
        updated = self.store.update(
            task["task_id"],
            status="dismissed",
            updated_at=self._utc_now(),
            resolved_at=self._utc_now(),
        )
        return self._enrich(updated)

    def reopen(self, task_id: str) -> Dict[str, Any]:
        task = self.get_task(task_id)
        if task["status"] not in TERMINAL_TASK_STATUSES:
            raise RepairTaskStateError("Only resolved repair tasks can be reopened")
        updated = self.store.update(
            task["task_id"],
            status="open",
            updated_at=self._utc_now(),
            resolved_at=None,
        )
        return self._enrich(updated)

    def record_verification(
        self,
        task_id: str,
        run: Dict[str, Any],
    ) -> Dict[str, Any]:
        task = self.get_task(task_id)
        if run.get("workspace") != task["workspace"]:
            raise RepairTaskStateError(
                "The verification run belongs to a different workspace"
            )
        status = "passed" if run.get("status") == "passed" else "failed"
        now = self._utc_now()
        self.store.add_attempt(
            task["task_id"],
            kind="verification",
            status=str(run.get("status") or "unknown"),
            run_id=run.get("run_id"),
            created_at=now,
        )
        updated = self.store.update(
            task["task_id"],
            status=status,
            updated_at=now,
            latest_run_id=run.get("run_id"),
            resolved_at=now if status == "passed" else None,
        )
        return self._enrich(updated)

    def start_agent_attempt(self, task_id: str) -> Dict[str, Any]:
        task = self.get_task(task_id)
        if task["status"] in TERMINAL_TASK_STATUSES:
            raise RepairTaskStateError(
                "Resolved repair tasks cannot start another agent attempt"
            )
        if task["status"] == "awaiting_review":
            raise RepairTaskStateError(
                "Review the pending proposals before asking the agent again"
            )
        if task["agent_attempt_count"] >= MAX_AGENT_ATTEMPTS:
            raise RepairTaskStateError(
                f"This repair reached the limit of {MAX_AGENT_ATTEMPTS} "
                "agent attempts. Run the check again to create a new failure "
                "cycle or inspect the issue manually."
            )
        self.store.add_attempt(
            task["task_id"],
            kind="agent",
            status="requested",
            created_at=self._utc_now(),
        )
        updated = self.store.update(
            task["task_id"],
            status="open",
            updated_at=self._utc_now(),
            resolved_at=None,
        )
        return self._enrich(updated)

    def _enrich(self, task: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(task)
        proposals = self.change_service.list_proposals(
            repair_task_id=task["task_id"]
        )
        result["proposals"] = proposals
        result["proposal_count"] = len(proposals)
        attempts = self.store.list_attempts(task["task_id"])
        for index, attempt in enumerate(attempts, start=1):
            attempt["sequence"] = index
        agent_attempt_count = sum(
            1 for attempt in attempts if attempt["kind"] == "agent"
        )
        result["attempts"] = attempts
        result["attempt_count"] = len(attempts)
        result["agent_attempt_count"] = agent_attempt_count
        result["max_agent_attempts"] = MAX_AGENT_ATTEMPTS
        result["can_start_agent_attempt"] = (
            task["status"] not in TERMINAL_TASK_STATUSES
            and task["status"] != "awaiting_review"
            and agent_attempt_count < MAX_AGENT_ATTEMPTS
        )

        if task["status"] not in TERMINAL_TASK_STATUSES and proposals:
            statuses = {proposal["status"] for proposal in proposals}
            if "pending" in statuses:
                result["status"] = "awaiting_review"
            elif statuses == {"approved"}:
                result["status"] = "ready_to_verify"
            elif statuses == {"rejected"}:
                result["status"] = "open"
        return result

    def _require_active_workspace(self, workspace: str) -> None:
        active = os.path.normcase(
            str(self.workspace_service.get_workspace().resolve())
        )
        if active != os.path.normcase(workspace):
            raise RepairTaskNotFoundError("Repair task not found in this workspace")

    @staticmethod
    def _required_id(value: str, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string")
        return value.strip()

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
