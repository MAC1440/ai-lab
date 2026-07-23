from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Dict
from uuid import uuid4

from services.change_service import ChangeService
from services.project_task_service import ProjectTaskService, ProjectTaskStateError
from services.repair_service import RepairService
from services.source_validation_service import SourceValidationService
from services.task_context_service import GeneratedChangeSet
from services.task_model_client import ModelStageResult, TaskModelClient
from services.verification_store import VerificationStore


class ProjectRepairOrchestrator:
    """Generate one bounded repair from a failed task verification."""

    def __init__(
        self,
        *,
        task_service: ProjectTaskService,
        change_service: ChangeService,
        repair_service: RepairService,
        verification_store: VerificationStore,
        model_client: TaskModelClient,
        source_validation_service: SourceValidationService,
        max_context_bytes: int = 240_000,
        max_failure_chars: int = 20_000,
    ) -> None:
        self.task_service = task_service
        self.change_service = change_service
        self.repair_service = repair_service
        self.verification_store = verification_store
        self.model_client = model_client
        self.source_validation_service = source_validation_service
        self.max_context_bytes = max_context_bytes
        self.max_failure_chars = max_failure_chars

    async def run_events(
        self,
        *,
        task_id: str,
        run_id: str,
    ) -> AsyncIterator[Dict[str, Any]]:
        task = self.task_service.get_task(task_id)
        repair_task_id = task.get("repair_task_id")
        verification_run_id = task.get("latest_verification_run_id")
        if task.get("phase") != "repairing" or not repair_task_id:
            raise ProjectTaskStateError(
                "A repair run requires a failed verification linked to the task"
            )
        if not verification_run_id:
            raise ProjectTaskStateError(
                "The task has no failed verification result to repair"
            )

        # Resolve the approved original paths before begin_orchestration replaces
        # current_change_set_id with the next repair proposal's future ID.
        allowed_paths = self._allowed_paths(task)
        self.task_service.begin_orchestration(
            task_id,
            run_id=run_id,
            stage="repair",
        )
        try:
            self.repair_service.start_agent_attempt(str(repair_task_id))
            yield {
                "type": "status",
                "run_id": run_id,
                "stage": "repair_context",
                "message": "Freezing failed output and affected current files",
            }
            task = self.task_service.get_task(task_id)
            verification = self.verification_store.get_run(
                str(verification_run_id)
            )
            context = self._compile_context(allowed_paths)
            prompt = self._repair_prompt(task, verification, context)
            self._require_prompt_budget(task, prompt)

            yield {
                "type": "repair_context",
                "run_id": run_id,
                "verification_run_id": verification_run_id,
                "allowed_paths": allowed_paths,
                "file_count": len(context),
            }
            result = await self.model_client.generate(
                agent_id=task["agent_id"],
                stage="repair",
                prompt=prompt,
                output_type=GeneratedChangeSet,
            )
            self._validate_output(result.output, allowed_paths)
            source_validation = self.source_validation_service.validate(
                result.output
            )
            self.task_service.record_artifact(
                task_id,
                artifact_type="repair_model_run",
                payload=self._model_artifact(
                    result,
                    verification_run_id=str(verification_run_id),
                    allowed_paths=allowed_paths,
                    source_validation=source_validation,
                ),
                run_id=run_id,
            )
            yield {
                "type": "source_validation",
                "run_id": run_id,
                "validation": source_validation,
            }

            change_set_id = uuid4().hex
            proposals = self.change_service.propose_change_set(
                operations=[
                    item.model_dump() for item in result.output.operations
                ],
                change_set_id=change_set_id,
                repair_task_id=str(repair_task_id),
            )
            completed = self.task_service.record_agent_result(
                task_id,
                run_id=run_id,
                result={"change_set_id": change_set_id},
            )
            yield {
                "type": "repair_change_set",
                "run_id": run_id,
                "change_set_id": change_set_id,
                "proposal_count": len(proposals),
                "proposals": proposals,
            }
            yield {"type": "done", "run_id": run_id, "task": completed}
        except asyncio.CancelledError:
            self.task_service.record_agent_interrupted(
                task_id,
                run_id=run_id,
                reason="Repair generation was cancelled by the user.",
            )
            raise
        except Exception as error:
            self.task_service.record_orchestration_failure(
                task_id,
                run_id=run_id,
                stage="repair",
                reason=str(error),
            )
            raise

    def _allowed_paths(self, task: Dict[str, Any]) -> list[str]:
        change_set_id = task.get("current_change_set_id")
        if not change_set_id:
            raise ProjectTaskStateError(
                "The failed task has no applied change set"
            )
        proposals = self.change_service.list_proposals(
            change_set_id=str(change_set_id)
        )
        if not proposals or {item["status"] for item in proposals} != {"approved"}:
            raise ProjectTaskStateError(
                "Repair generation requires a fully applied original change set"
            )
        paths: list[str] = []
        for proposal in proposals:
            for path in (
                proposal.get("file_path"),
                proposal.get("destination_path"),
            ):
                clean = str(path or "").strip()
                if clean and clean not in paths:
                    paths.append(clean)
        return paths

    def _compile_context(self, allowed_paths: list[str]) -> list[Dict[str, Any]]:
        root = self.task_service.workspace_service.get_workspace().resolve()
        result: list[Dict[str, Any]] = []
        used = 0
        for relative in allowed_paths:
            target = (root / relative).resolve()
            try:
                target.relative_to(root)
            except ValueError as error:
                raise ValueError(
                    f"Repair path escapes workspace: {relative}"
                ) from error
            if not target.is_file():
                continue
            raw = target.read_bytes()
            if used + len(raw) > self.max_context_bytes:
                raise ValueError(
                    "Repair context exceeds its safe byte budget; split the task"
                )
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ValueError(
                    f"Repair target is not UTF-8 text: {relative}"
                ) from error
            result.append({"path": relative, "content": content})
            used += len(raw)
        if not result:
            raise ValueError("No current text files are available for repair")
        return result

    def _require_prompt_budget(self, task: Dict[str, Any], prompt: str) -> None:
        budget = self.model_client.prompt_budget(
            agent_id=task["agent_id"],
            stage="repair",
        )
        required = self.model_client.estimate_tokens(
            agent_id=task["agent_id"],
            stage="repair",
            text=prompt,
        )
        if required > budget:
            raise ValueError(
                f"The repair prompt requires about {required:,} tokens but the "
                f"selected repair model allows {budget:,} safe input tokens."
            )

    @staticmethod
    def _validate_output(
        generated: GeneratedChangeSet,
        allowed_paths: list[str],
    ) -> None:
        allowed = {
            ProjectRepairOrchestrator._path_key(path)
            for path in allowed_paths
        }
        for operation in generated.operations:
            if (
                ProjectRepairOrchestrator._path_key(operation.path)
                not in allowed
            ):
                raise ValueError(
                    "Repair attempted to change an unrelated file: "
                    f"{operation.path}"
                )
            if operation.operation != "update":
                raise ValueError(
                    "Repair operations are limited to updates of files from the "
                    f"failed change set: {operation.path}"
                )

    @staticmethod
    def _path_key(path: str) -> str:
        """Return a platform-independent key for an already validated path."""

        return str(path).replace("\\", "/").casefold()

    def _repair_prompt(
        self,
        task: Dict[str, Any],
        verification: Dict[str, Any],
        context: list[Dict[str, Any]],
    ) -> str:
        failure = "\n\n".join(
            part
            for part in (
                str(verification.get("output") or ""),
                str(verification.get("error") or ""),
            )
            if part.strip()
        )[-self.max_failure_chars :]
        sections = [
            (
                f"<workspace_file path={json.dumps(item['path'])}>\n"
                f"{item['content']}\n</workspace_file>"
            )
            for item in context
        ]
        return "\n\n".join(
            (
                "Repair this failed bounded task. Return one structured change "
                "set containing only complete-file updates for the supplied "
                "workspace files. Do not create, delete, move, or mention any "
                "other file. Make the smallest coherent correction.",
                f"Original goal: {task['goal']}",
                "Verification failure:\n" + (failure or "[No output captured]"),
                "Current affected files:\n" + "\n\n".join(sections),
            )
        )

    @staticmethod
    def _model_artifact(
        result: ModelStageResult[GeneratedChangeSet],
        **extra: Any,
    ) -> Dict[str, Any]:
        return {
            "output": result.output.model_dump(),
            "usage": result.usage,
            "model": result.model,
            "provider_id": result.provider_id,
            "capability": result.capability,
            **extra,
        }
