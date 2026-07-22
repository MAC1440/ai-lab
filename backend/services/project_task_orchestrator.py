from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Dict
from uuid import uuid4

from services.change_service import ChangeService
from services.project_context_service import ProjectContextService
from services.project_task_service import ProjectTaskService
from services.task_context_service import (
    GeneratedChangeSet,
    ImplementationPlan,
)
from services.task_model_client import ModelStageResult, TaskModelClient


TaskEvent = Dict[str, Any]


class ProjectTaskOrchestrator:
    """Own the deterministic plan -> context -> generate task workflow."""

    def __init__(
        self,
        *,
        task_service: ProjectTaskService,
        project_context_service: ProjectContextService,
        change_service: ChangeService,
        model_client: TaskModelClient,
    ) -> None:
        self.task_service = task_service
        self.project_context_service = project_context_service
        self.change_service = change_service
        self.model_client = model_client

    async def run_events(
        self,
        *,
        task_id: str,
        run_id: str,
    ) -> AsyncIterator[TaskEvent]:
        initial = self.task_service.get_task(task_id)
        resume_generation = self._can_resume_generation(initial)
        stage = "generation" if resume_generation else "planning"
        self.task_service.begin_orchestration(
            task_id,
            run_id=run_id,
            stage=stage,
        )

        try:
            yield self._status(
                run_id,
                "planning" if stage == "planning" else "generation",
                (
                    "Creating a typed implementation plan"
                    if stage == "planning"
                    else "Resuming from the frozen context pack"
                ),
            )

            if stage == "planning":
                plan_result, trace = await self._plan(task_id)
                self.task_service.record_artifact(
                    task_id,
                    artifact_type="planning_model_run",
                    payload=self._model_artifact(plan_result, trace=trace),
                    run_id=run_id,
                )
                task = self.task_service.save_plan(
                    task_id,
                    plan_result.output.model_dump(),
                    run_id=run_id,
                )
                yield {
                    "type": "plan",
                    "run_id": run_id,
                    "plan": plan_result.output.model_dump(),
                    "task": task,
                }

                yield self._status(
                    run_id,
                    "context",
                    "Freezing exact existing files and SHA-256 hashes",
                )
                task = self.task_service.compile_context(
                    task_id,
                    run_id=run_id,
                )
                context = self._latest_payload(task, "context_pack")
                yield {
                    "type": "context",
                    "run_id": run_id,
                    "context": self._context_summary(context),
                }

            yield self._status(
                run_id,
                "generation",
                "Generating one typed multi-file change set",
            )
            generated_result = await self._generate(task_id)
            task = self.task_service.get_task(task_id)
            plan = ImplementationPlan.model_validate(
                self._latest_payload(task, "implementation_plan")
            )
            context = self._latest_payload(task, "context_pack")

            yield self._status(
                run_id,
                "validation",
                "Checking plan alignment and stale workspace content",
            )
            self._validate_generated(plan, generated_result.output)
            self.task_service.task_context_service.assert_fresh(context)
            self.task_service.validate_plan_workspace(plan)

            change_set_id = uuid4().hex
            proposals = self.change_service.propose_change_set(
                operations=[
                    item.model_dump()
                    for item in generated_result.output.operations
                ],
                change_set_id=change_set_id,
                repair_task_id=task.get("repair_task_id"),
            )
            self.task_service.record_artifact(
                task_id,
                artifact_type="generation_model_run",
                payload=self._model_artifact(
                    generated_result,
                    change_set_id=change_set_id,
                    proposal_count=len(proposals),
                ),
                run_id=run_id,
            )
            completed = self.task_service.record_agent_result(
                task_id,
                run_id=run_id,
                result={"change_set_id": change_set_id},
            )
            yield {
                "type": "change_set",
                "run_id": run_id,
                "change_set_id": change_set_id,
                "proposal_count": len(proposals),
                "proposals": proposals,
            }
            yield {
                "type": "done",
                "run_id": run_id,
                "task": completed,
            }
        except asyncio.CancelledError:
            self.task_service.record_agent_interrupted(
                task_id,
                run_id=run_id,
                reason="Project task generation was cancelled by the user.",
            )
            raise
        except Exception as error:
            self.task_service.record_orchestration_failure(
                task_id,
                run_id=run_id,
                stage=stage,
                reason=str(error),
            )
            raise

    async def _plan(
        self,
        task_id: str,
    ) -> tuple[ModelStageResult[ImplementationPlan], Dict[str, Any]]:
        task = self.task_service.get_task(task_id)
        trace, project_context = self.project_context_service.build(
            prompt=f"{task['title']}\n{task['goal']}",
            agent_id=task["agent_id"],
        )
        prompt = self._planning_prompt(task, project_context)
        self._require_prompt_budget(task, "planning", prompt)
        result = await self.model_client.generate(
            agent_id=task["agent_id"],
            stage="planning",
            prompt=prompt,
            output_type=ImplementationPlan,
        )
        self.task_service.validate_plan_workspace(result.output)
        return result, trace

    async def _generate(
        self,
        task_id: str,
    ) -> ModelStageResult[GeneratedChangeSet]:
        task = self.task_service.get_task(task_id)
        plan = ImplementationPlan.model_validate(
            self._latest_payload(task, "implementation_plan")
        )
        context = self._latest_payload(task, "context_pack")
        self.task_service.task_context_service.assert_fresh(context)
        self.task_service.validate_plan_workspace(plan)
        prompt = self._generation_prompt(task, plan, context)
        self._require_prompt_budget(task, "generation", prompt)
        return await self.model_client.generate(
            agent_id=task["agent_id"],
            stage="generation",
            prompt=prompt,
            output_type=GeneratedChangeSet,
        )

    def _require_prompt_budget(
        self,
        task: Dict[str, Any],
        stage: str,
        prompt: str,
    ) -> None:
        budget = self.model_client.prompt_budget(
            agent_id=task["agent_id"],
            stage=stage,
        )
        if len(prompt) > budget:
            raise ValueError(
                f"The {stage} prompt requires {len(prompt):,} characters but "
                f"the selected model's safe budget is {budget:,}. Split the "
                "task, reduce affected files, or configure a model with a "
                "larger context window. No source file was truncated."
            )

    @staticmethod
    def _validate_generated(
        plan: ImplementationPlan,
        generated: GeneratedChangeSet,
    ) -> None:
        planned = {
            item.path.casefold(): (
                item.operation,
                item.destination_path.casefold()
                if item.destination_path
                else None,
            )
            for item in plan.files
        }
        produced = {
            item.path.casefold(): (
                item.operation,
                item.destination_path.casefold()
                if item.destination_path
                else None,
            )
            for item in generated.operations
        }
        missing = sorted(set(planned) - set(produced))
        extra = sorted(set(produced) - set(planned))
        if missing or extra:
            details = []
            if missing:
                details.append("missing: " + ", ".join(missing))
            if extra:
                details.append("unplanned: " + ", ".join(extra))
            raise ValueError(
                "Generated change set does not match the approved plan ("
                + "; ".join(details)
                + ")"
            )
        mismatched = [
            path
            for path, expectation in planned.items()
            if produced[path] != expectation
        ]
        if mismatched:
            raise ValueError(
                "Generated operations changed planned operation types or move "
                "destinations: " + ", ".join(sorted(mismatched))
            )

    @staticmethod
    def _planning_prompt(task: Dict[str, Any], project_context: str) -> str:
        return "\n\n".join(
            (
                "Plan this bounded project task. Use exact workspace-relative "
                "paths visible in the deterministic context. Mark an existing "
                "file as update/delete/move and a genuinely new file as create. "
                "Normally use at most eight files; never exceed twenty. Do not "
                "write source code in the plan.",
                f"Task title: {task['title']}\nTask goal: {task['goal']}",
                project_context,
            )
        )

    @staticmethod
    def _generation_prompt(
        task: Dict[str, Any],
        plan: ImplementationPlan,
        context: Dict[str, Any],
    ) -> str:
        file_sections = []
        for item in context.get("files", []):
            file_sections.append(
                f"<workspace_file path={json.dumps(item['path'])} "
                f"sha256={json.dumps(item['sha256'])}>\n"
                f"{item['content']}\n</workspace_file>"
            )
        return "\n\n".join(
            (
                "Generate the planned change set exactly. Include every planned "
                "operation once and no others. For create/update, content must "
                "be the complete desired UTF-8 file—not a diff, placeholder, or "
                "partial excerpt. Delete/move operations must not contain content.",
                f"Task title: {task['title']}\nTask goal: {task['goal']}",
                "Approved plan:\n" + plan.model_dump_json(indent=2),
                "Frozen existing files:\n" + (
                    "\n\n".join(file_sections)
                    if file_sections
                    else "[No existing files are changed by this plan.]"
                ),
            )
        )

    @staticmethod
    def _latest_payload(task: Dict[str, Any], artifact_type: str) -> Dict[str, Any]:
        for artifact in reversed(task.get("artifacts", [])):
            if artifact.get("artifact_type") == artifact_type:
                return dict(artifact["payload"])
        raise ValueError(f"Task has no {artifact_type} artifact")

    @classmethod
    def _can_resume_generation(cls, task: Dict[str, Any]) -> bool:
        artifact_types = {
            item.get("artifact_type") for item in task.get("artifacts", [])
        }
        return (
            task.get("phase") in {"generation", "generation_failed", "interrupted"}
            and {"implementation_plan", "context_pack"}.issubset(artifact_types)
        )

    @staticmethod
    def _context_summary(context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "version": context.get("version"),
            "workspace": context.get("workspace"),
            "file_count": len(context.get("files", [])),
            "files": [
                {
                    "path": item.get("path"),
                    "sha256": item.get("sha256"),
                    "bytes": item.get("bytes"),
                }
                for item in context.get("files", [])
            ],
            "bytes": context.get("bytes"),
            "complete": context.get("complete"),
            "omitted": context.get("omitted", []),
        }

    @staticmethod
    def _model_artifact(
        result: ModelStageResult[Any],
        **extra: Any,
    ) -> Dict[str, Any]:
        return {
            "model": result.model,
            "provider_id": result.provider_id,
            "usage": result.usage,
            "output": result.output.model_dump(),
            **extra,
        }

    @staticmethod
    def _status(run_id: str, stage: str, message: str) -> TaskEvent:
        return {
            "type": "status",
            "run_id": run_id,
            "stage": stage,
            "message": message,
        }
