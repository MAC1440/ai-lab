from __future__ import annotations

from typing import Any, AsyncIterator, Dict, Iterable

from services.change_service import ChangeService
from services.project_detection_service import ProjectDetectionService
from services.project_task_service import ProjectTaskService, ProjectTaskStateError
from services.repair_service import RepairService
from services.verification_service import VerificationService


class VerificationProfileSelectionError(ValueError):
    """Raised when a task has no safe automatic verification profile."""


class ProjectTaskCompletionService:
    """Apply an approved task and immediately verify the resulting workspace."""

    def __init__(
        self,
        *,
        task_service: ProjectTaskService,
        change_service: ChangeService,
        project_detection_service: ProjectDetectionService,
        verification_service: VerificationService,
        repair_service: RepairService,
    ) -> None:
        self.task_service = task_service
        self.change_service = change_service
        self.project_detection_service = project_detection_service
        self.verification_service = verification_service
        self.repair_service = repair_service

    async def approve_and_verify_events(
        self,
        *,
        task_id: str,
    ) -> AsyncIterator[Dict[str, Any]]:
        task = self.task_service.get_task(task_id)
        retrying_verification = (
            task["status"] == "ready_to_verify"
            or (
                task["status"] == "paused"
                and task.get("phase") == "verification_cancelled"
            )
        )
        if task["status"] != "awaiting_approval" and not retrying_verification:
            raise ProjectTaskStateError(
                "The task must be awaiting approval or ready to retry "
                "verification"
            )
        change_set_id = task.get("current_change_set_id")
        if not change_set_id:
            raise ProjectTaskStateError("The task has no current change set")

        profile_id = self.select_profile(task)
        if retrying_verification:
            proposals = task.get("proposals", [])
            if not proposals or {
                item.get("status") for item in proposals
            } != {"approved"}:
                raise ProjectTaskStateError(
                    "Verification retry requires a fully applied change set"
                )
            yield {
                "type": "status",
                "stage": "approval",
                "message": "Change set is already applied; retrying checks",
                "change_set_id": change_set_id,
                "verification_profile_id": profile_id,
            }
        else:
            yield {
                "type": "status",
                "stage": "approval",
                "message": "Applying the complete change set transactionally",
                "change_set_id": change_set_id,
                "verification_profile_id": profile_id,
            }
            proposals = self.change_service.approve_change_set(change_set_id)
            yield {
                "type": "change_set_applied",
                "change_set_id": change_set_id,
                "proposals": proposals,
            }

        yield {
            "type": "status",
            "stage": "verification",
            "message": "Running the selected verification profile",
            "verification_profile_id": profile_id,
        }
        async for event in self.verification_service.run_events(
            profile_id=profile_id,
            proposal_id=None,
        ):
            if event.get("type") == "verification_started":
                self.task_service.record_verification_started(
                    task_id,
                    run_id=str(event["run_id"]),
                    profile_id=profile_id,
                )
            elif event.get("type") == "verification_done":
                run = dict(event["result"])
                repair_task_id = None
                if run.get("status") in {"failed", "error", "timed_out"}:
                    repair = self.repair_service.create_from_verification(
                        str(run["run_id"])
                    )
                    repair_task_id = str(repair["task_id"])
                    event = {
                        **event,
                        "repair_task": repair,
                    }
                completed = self.task_service.record_verification_result(
                    task_id,
                    run=run,
                    repair_task_id=repair_task_id,
                )
                event = {**event, "task": completed}
            yield event

    def select_profile(self, task: Dict[str, Any]) -> str:
        inspection = self.project_detection_service.inspect_workspace()
        profiles = [
            item for item in inspection.get("profiles", []) if item.get("available")
        ]
        requested = task.get("verification_profile_id")
        if requested:
            for profile in profiles:
                if profile.get("profile_id") == requested:
                    return str(requested)
            raise VerificationProfileSelectionError(
                "The task's selected verification profile is not currently "
                f"available: {requested}"
            )
        if not profiles:
            raise VerificationProfileSelectionError(
                "No available verification profile was detected. Configure a "
                "test, type-check, build, .NET, or Unity compile profile before "
                "approving this production task."
            )

        hints = self._verification_hints(task)
        affected = self._affected_paths(task)
        agent_id = str(task.get("agent_id") or "")
        scored = [
            (self._profile_score(profile, hints, affected, agent_id), profile)
            for profile in profiles
        ]
        scored.sort(
            key=lambda item: (
                -item[0],
                str(item[1].get("working_directory") or ""),
                str(item[1].get("profile_id") or ""),
            )
        )
        return str(scored[0][1]["profile_id"])

    @staticmethod
    def _verification_hints(task: Dict[str, Any]) -> set[str]:
        for artifact in reversed(task.get("artifacts", [])):
            if artifact.get("artifact_type") == "implementation_plan":
                values = artifact.get("payload", {}).get("verification", [])
                return {
                    token
                    for value in values
                    for token in ProjectTaskCompletionService._tokens(str(value))
                }
        return set()

    @staticmethod
    def _affected_paths(task: Dict[str, Any]) -> list[str]:
        return [
            str(item.get("file_path") or "").replace("\\", "/")
            for item in task.get("proposals", [])
        ]

    @classmethod
    def _profile_score(
        cls,
        profile: Dict[str, Any],
        hints: set[str],
        affected: Iterable[str],
        agent_id: str,
    ) -> int:
        searchable = " ".join(
            str(profile.get(name) or "")
            for name in (
                "profile_id",
                "name",
                "description",
                "project_type",
                "command",
            )
        )
        tokens = cls._tokens(searchable)
        score = len(tokens.intersection(hints)) * 30

        project_type = str(profile.get("project_type") or "")
        if agent_id == "unity" and project_type == "unity":
            score += 100
        elif agent_id == "web" and project_type == "node":
            score += 80
        elif agent_id == "coding" and project_type in {"python", "node", "dotnet"}:
            score += 30

        working_directory = str(profile.get("working_directory") or ".")
        normalized_root = "" if working_directory == "." else (
            working_directory.replace("\\", "/").strip("/") + "/"
        )
        if any(path.startswith(normalized_root) for path in affected):
            score += 40

        preference = {
            "test": 25,
            "pytest": 25,
            "typecheck": 22,
            "compile": 20,
            "lint": 12,
            "build": 10,
        }
        score += max(
            (weight for token, weight in preference.items() if token in tokens),
            default=0,
        )
        return score

    @staticmethod
    def _tokens(value: str) -> set[str]:
        normalized = "".join(
            character.lower() if character.isalnum() else " "
            for character in value
        )
        return {token for token in normalized.split() if token}
