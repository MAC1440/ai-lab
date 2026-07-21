from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.change_service import ChangeService
from services.project_task_store import (
    ProjectTaskNotFoundError,
    ProjectTaskStore,
)
from services.workspace_service import WorkspaceService


TERMINAL_STATUSES = {"completed", "cancelled"}


class ProjectTaskStateError(RuntimeError):
    """Raised when a project task cannot make the requested transition."""


class ProjectTaskService:
    """Coordinate durable agent, approval, verification, and repair stages."""

    def __init__(
        self,
        *,
        workspace_service: WorkspaceService,
        change_service: ChangeService,
        store: ProjectTaskStore,
    ) -> None:
        self.workspace_service = workspace_service
        self.change_service = change_service
        self.store = store

    def create(
        self,
        *,
        title: str,
        goal: str,
        agent_id: str,
        verification_profile_id: Optional[str] = None,
        max_attempts: int = 3,
    ) -> Dict[str, Any]:
        clean_title = self._required_text(title, "title", 160)
        clean_goal = self._required_text(goal, "goal", 12_000)
        clean_agent = self._required_text(agent_id, "agent_id", 100)
        if max_attempts < 1 or max_attempts > 5:
            raise ValueError("max_attempts must be between 1 and 5")

        now = self._utc_now()
        task = self.store.create(
            {
                "task_id": uuid4().hex,
                "workspace": str(
                    self.workspace_service.get_workspace().resolve()
                ),
                "title": clean_title,
                "goal": clean_goal,
                "agent_id": clean_agent,
                "status": "queued",
                "phase": "planning",
                "verification_profile_id": self._optional_id(
                    verification_profile_id
                ),
                "attempt_count": 0,
                "max_attempts": max_attempts,
                "created_at": now,
                "updated_at": now,
            }
        )
        self._event(task["task_id"], "created", "Project task created.")
        return self._enrich(task)

    def list_tasks(self, *, limit: int = 50) -> List[Dict[str, Any]]:
        workspace = str(self.workspace_service.get_workspace().resolve())
        return [
            self._enrich(task)
            for task in self.store.list(workspace=workspace, limit=limit)
        ]

    def get_task(self, task_id: str) -> Dict[str, Any]:
        task = self.store.get(self._required_id(task_id))
        self._require_active_workspace(task["workspace"])
        return self._enrich(task)

    def start_agent_run(self, task_id: str, run_id: str) -> Dict[str, Any]:
        task = self.get_task(task_id)
        if task["status"] in TERMINAL_STATUSES:
            raise ProjectTaskStateError(
                "A completed or cancelled project task cannot start an agent run"
            )
        if task["status"] in {"awaiting_approval", "ready_to_verify"}:
            raise ProjectTaskStateError(
                "Review or verify the current change set before continuing"
            )
        if task["attempt_count"] >= task["max_attempts"]:
            raise ProjectTaskStateError(
                "This task reached its configured agent-attempt limit"
            )
        now = self._utc_now()
        updated = self.store.update(
            task["task_id"],
            status="running",
            phase="proposing",
            current_agent_run_id=self._required_id(run_id),
            current_change_set_id=None,
            last_error=None,
            attempt_count=task["attempt_count"] + 1,
            updated_at=now,
            completed_at=None,
            cancelled_at=None,
        )
        self._event(
            task["task_id"],
            "agent_started",
            "Agent execution started.",
            {"run_id": run_id, "attempt": updated["attempt_count"]},
        )
        return self._enrich(updated)

    def record_agent_result(
        self,
        task_id: str,
        *,
        run_id: str,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        task = self.get_task(task_id)
        self._require_current_agent_run(task, run_id)
        change_set_id = result.get("change_set_id")
        proposals = (
            self.change_service.list_proposals(change_set_id=change_set_id)
            if change_set_id
            else []
        )
        now = self._utc_now()
        if proposals:
            status = "awaiting_approval"
            phase = "review"
            last_error = None
            message = f"Agent proposed {len(proposals)} file change(s)."
        else:
            status = "needs_attention"
            phase = "proposal_missing"
            last_error = (
                "The agent completed without creating a validated file change set."
            )
            message = last_error
        updated = self.store.update(
            task["task_id"],
            status=status,
            phase=phase,
            current_agent_run_id=None,
            current_change_set_id=change_set_id,
            last_error=last_error,
            updated_at=now,
        )
        self._event(
            task["task_id"],
            "agent_finished",
            message,
            {"run_id": run_id, "change_set_id": change_set_id},
        )
        return self._enrich(updated)

    def record_agent_interrupted(
        self,
        task_id: str,
        *,
        run_id: str,
        reason: str,
    ) -> Dict[str, Any]:
        task = self.get_task(task_id)
        if task.get("current_agent_run_id") != run_id:
            return task
        updated = self.store.update(
            task["task_id"],
            status="paused",
            phase="interrupted",
            current_agent_run_id=None,
            last_error=reason,
            updated_at=self._utc_now(),
        )
        self._event(task["task_id"], "agent_interrupted", reason)
        return self._enrich(updated)

    def resume(self, task_id: str) -> Dict[str, Any]:
        task = self.get_task(task_id)
        if task["status"] in TERMINAL_STATUSES:
            raise ProjectTaskStateError(
                "A completed or cancelled project task cannot be resumed"
            )
        if task["status"] in {"running", "verifying"}:
            raise ProjectTaskStateError("The project task is already active")
        if task["status"] in {"awaiting_approval", "ready_to_verify"}:
            raise ProjectTaskStateError(
                "Review or verify the current change set instead of resuming"
            )
        updated = self.store.update(
            task["task_id"],
            status="queued",
            phase="planning" if not task.get("repair_task_id") else "repairing",
            current_agent_run_id=None,
            current_change_set_id=None,
            last_error=None,
            updated_at=self._utc_now(),
        )
        self._event(task["task_id"], "resumed", "Project task queued again.")
        return self._enrich(updated)

    def record_verification_started(
        self,
        task_id: str,
        *,
        run_id: str,
        profile_id: str,
    ) -> Dict[str, Any]:
        task = self.get_task(task_id)
        if task["status"] not in {"ready_to_verify", "needs_attention"}:
            raise ProjectTaskStateError(
                "Approve the task's current proposals before verification"
            )
        updated = self.store.update(
            task["task_id"],
            status="verifying",
            phase="verification",
            verification_profile_id=profile_id,
            latest_verification_run_id=run_id,
            last_error=None,
            updated_at=self._utc_now(),
        )
        self._event(
            task["task_id"],
            "verification_started",
            "Workspace verification started.",
            {"run_id": run_id, "profile_id": profile_id},
        )
        return self._enrich(updated)

    def record_verification_result(
        self,
        task_id: str,
        *,
        run: Dict[str, Any],
        repair_task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        task = self.get_task(task_id)
        if run.get("workspace") != task["workspace"]:
            raise ProjectTaskStateError(
                "The verification result belongs to another workspace"
            )
        passed = run.get("status") == "passed"
        cancelled = run.get("status") == "cancelled"
        if passed:
            status, phase = "completed", "completed"
            error = None
        elif cancelled:
            status, phase = "paused", "verification_cancelled"
            error = "Verification was cancelled before completion."
        else:
            status, phase = "needs_attention", "repairing"
            error = run.get("error") or "Verification failed."
        now = self._utc_now()
        updated = self.store.update(
            task["task_id"],
            status=status,
            phase=phase,
            latest_verification_run_id=run.get("run_id"),
            repair_task_id=repair_task_id,
            last_error=error,
            updated_at=now,
            completed_at=now if passed else None,
        )
        self._event(
            task["task_id"],
            "verification_finished",
            f"Verification finished with status {run.get('status', 'unknown')}.",
            {
                "run_id": run.get("run_id"),
                "status": run.get("status"),
                "repair_task_id": repair_task_id,
            },
        )
        return self._enrich(updated)

    def cancel(self, task_id: str) -> Dict[str, Any]:
        task = self.get_task(task_id)
        if task["status"] == "completed":
            raise ProjectTaskStateError("A completed project task cannot be cancelled")
        if task["status"] == "cancelled":
            return task
        now = self._utc_now()
        updated = self.store.update(
            task["task_id"],
            status="cancelled",
            phase="cancelled",
            current_agent_run_id=None,
            cancelled_at=now,
            updated_at=now,
        )
        self._event(task["task_id"], "cancelled", "Project task cancelled.")
        return self._enrich(updated)

    def execution_prompt(self, task: Dict[str, Any]) -> str:
        repair_note = (
            "This is a repair iteration. Read the latest verification output "
            "provided by the repair workflow before proposing changes."
            if task.get("repair_task_id")
            else ""
        )
        return "\n".join(
            part
            for part in (
                "Execute this bounded project task as a reviewable change set.",
                f"Task: {task['title']}",
                f"Goal: {task['goal']}",
                repair_note,
                "First inspect the deterministic project context and read every existing file you intend to modify.",
                "Create a concise implementation plan, then use propose_file_change_set once for all related creates and updates.",
                "Keep the change set coherent and within 20 files. Do not write files directly and do not claim completion before approval and verification.",
                "If the goal cannot be completed safely, explain the blocker without proposing unrelated changes.",
            )
            if part
        )

    def _enrich(self, task: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(task)
        change_set_id = task.get("current_change_set_id")
        proposals = (
            self.change_service.list_proposals(change_set_id=change_set_id)
            if change_set_id
            else []
        )
        result["proposals"] = proposals
        result["proposal_count"] = len(proposals)
        result["events"] = self.store.list_events(task["task_id"])

        if task["status"] not in TERMINAL_STATUSES and proposals:
            statuses = {proposal["status"] for proposal in proposals}
            if "pending" in statuses:
                result["status"] = "awaiting_approval"
                result["phase"] = "review"
            elif statuses == {"approved"} and task["status"] != "verifying":
                result["status"] = "ready_to_verify"
                result["phase"] = "verification"
            elif "rejected" in statuses:
                result["status"] = "needs_attention"
                result["phase"] = "changes_rejected"

        result["can_resume"] = (
            result["status"] in {"queued", "paused", "needs_attention"}
            and result["attempt_count"] < result["max_attempts"]
        )
        result["execution_prompt"] = self.execution_prompt(result)
        return result

    def _require_current_agent_run(
        self, task: Dict[str, Any], run_id: str
    ) -> None:
        if task.get("current_agent_run_id") != run_id:
            raise ProjectTaskStateError(
                "The agent result does not match this task's active run"
            )

    def _require_active_workspace(self, workspace: str) -> None:
        active = os.path.normcase(
            str(self.workspace_service.get_workspace().resolve())
        )
        if active != os.path.normcase(workspace):
            raise ProjectTaskNotFoundError(
                "Project task not found in the active workspace"
            )

    def _event(
        self,
        task_id: str,
        event_type: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.store.add_event(
            task_id,
            event_type=event_type,
            message=message,
            payload=payload,
            created_at=self._utc_now(),
        )

    @staticmethod
    def _required_id(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("ID must be a non-empty string")
        return value.strip()

    @staticmethod
    def _optional_id(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return ProjectTaskService._required_id(value)

    @staticmethod
    def _required_text(value: str, name: str, max_length: int) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
        clean = value.strip()
        if len(clean) > max_length:
            raise ValueError(f"{name} must not exceed {max_length} characters")
        return clean

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
