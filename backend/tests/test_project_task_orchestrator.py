import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Type

from pydantic import BaseModel

from services.change_service import ChangeService
from services.project_task_orchestrator import ProjectTaskOrchestrator
from services.project_task_service import ProjectTaskService
from services.project_task_store import ProjectTaskStore
from services.task_context_service import (
    GeneratedChangeSet,
    ImplementationPlan,
)
from services.task_model_client import ModelStageResult


class TemporaryWorkspaceService:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def get_workspace(self) -> Path:
        return self.root

    def resolve_workspace_path(self, relative_path: str) -> Path:
        target = (self.root / relative_path).resolve()
        target.relative_to(self.root)
        return target


class FakeProjectContextService:
    def build(self, *, prompt: str, agent_id: str):
        return (
            {"enabled": True, "agent_id": agent_id, "characters": len(prompt)},
            "Selected project root: .\nAssets/Player.cs\nPackages/manifest.json",
        )


class FakeTaskModelClient:
    def __init__(
        self,
        *,
        plan: ImplementationPlan,
        change_set: GeneratedChangeSet,
        mutate_during_generation=None,
        budget: int = 200_000,
    ) -> None:
        self.plan = plan
        self.change_set = change_set
        self.mutate_during_generation = mutate_during_generation
        self.budget = budget
        self.calls: list[str] = []

    def prompt_budget(self, *, agent_id: str, stage: str) -> int:
        del agent_id, stage
        return self.budget

    def estimate_tokens(
        self,
        *,
        agent_id: str,
        stage: str,
        text: str,
    ) -> int:
        del agent_id, stage
        return len(text)

    async def generate(
        self,
        *,
        agent_id: str,
        stage: str,
        prompt: str,
        output_type: Type[BaseModel],
    ) -> ModelStageResult:
        del agent_id, prompt
        self.calls.append(stage)
        if stage == "planning":
            output = output_type.model_validate(self.plan.model_dump())
        else:
            if self.mutate_during_generation is not None:
                self.mutate_during_generation()
            output = output_type.model_validate(self.change_set.model_dump())
        return ModelStageResult(
            output=output,
            usage={"requests": 1, "input_tokens": 100, "output_tokens": 50},
            model="fake-coder",
            provider_id="test",
            capability={"profile_source": "saved"},
        )


class ProjectTaskOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "Assets").mkdir()
        (self.root / "Assets" / "Player.cs").write_text(
            "public class Player {}\n",
            encoding="utf-8",
        )
        self.workspace = TemporaryWorkspaceService(self.root)
        self.changes = ChangeService(self.workspace)
        self.task_service = ProjectTaskService(
            workspace_service=self.workspace,
            change_service=self.changes,
            store=ProjectTaskStore(self.root / "tasks.sqlite3"),
        )
        self.plan = ImplementationPlan.model_validate(
            {
                "summary": "Add reusable player health.",
                "files": [
                    {
                        "path": "Assets/Player.cs",
                        "operation": "update",
                        "reason": "Connect Player to the health component.",
                    },
                    {
                        "path": "Assets/Health.cs",
                        "operation": "create",
                        "reason": "Implement reusable health state.",
                    },
                ],
                "verification": ["unity-compile"],
            }
        )
        self.generated = GeneratedChangeSet.model_validate(
            {
                "summary": "Add player health.",
                "operations": [
                    {
                        "path": "Assets/Player.cs",
                        "operation": "update",
                        "summary": "Use Health from Player.",
                        "content": "public class Player { public Health Health; }\n",
                    },
                    {
                        "path": "Assets/Health.cs",
                        "operation": "create",
                        "summary": "Add health state.",
                        "content": "public class Health {}\n",
                    },
                ],
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_task(self) -> Dict[str, Any]:
        return self.task_service.create(
            title="Add player health",
            goal="Create Health and connect it to Player.",
            agent_id="unity",
        )

    def orchestrator(self, client: FakeTaskModelClient):
        return ProjectTaskOrchestrator(
            task_service=self.task_service,
            project_context_service=FakeProjectContextService(),
            change_service=self.changes,
            model_client=client,
        )

    async def test_runs_typed_plan_and_generation_as_separate_calls(self):
        task = self.create_task()
        client = FakeTaskModelClient(plan=self.plan, change_set=self.generated)

        events = [
            event
            async for event in self.orchestrator(client).run_events(
                task_id=task["task_id"],
                run_id="structured-run-123",
            )
        ]

        self.assertEqual(client.calls, ["planning", "generation"])
        self.assertEqual(events[-1]["type"], "done")
        completed = events[-1]["task"]
        self.assertEqual(completed["status"], "awaiting_approval")
        self.assertEqual(completed["proposal_count"], 2)
        self.assertFalse((self.root / "Assets" / "Health.cs").exists())
        artifact_types = [
            item["artifact_type"] for item in completed["artifacts"]
        ]
        self.assertIn("implementation_plan", artifact_types)
        self.assertIn("context_pack", artifact_types)
        self.assertIn("planning_model_run", artifact_types)
        self.assertIn("generation_model_run", artifact_types)

    async def test_rejects_unplanned_generated_file_without_proposals(self):
        task = self.create_task()
        invalid = self.generated.model_copy(deep=True)
        invalid.operations[1].path = "Assets/Unplanned.cs"
        client = FakeTaskModelClient(plan=self.plan, change_set=invalid)

        with self.assertRaisesRegex(ValueError, "does not match the approved plan"):
            async for _ in self.orchestrator(client).run_events(
                task_id=task["task_id"],
                run_id="structured-run-456",
            ):
                pass

        failed = self.task_service.get_task(task["task_id"])
        self.assertEqual(failed["status"], "needs_attention")
        self.assertEqual(failed["phase"], "generation_failed")
        self.assertEqual(self.changes.list_proposals(), [])

    async def test_rejects_source_changed_during_generation(self):
        task = self.create_task()

        def mutate_source():
            (self.root / "Assets" / "Player.cs").write_text(
                "public class Player { public int Changed; }\n",
                encoding="utf-8",
            )

        client = FakeTaskModelClient(
            plan=self.plan,
            change_set=self.generated,
            mutate_during_generation=mutate_source,
        )

        with self.assertRaisesRegex(ValueError, "changed after planning"):
            async for _ in self.orchestrator(client).run_events(
                task_id=task["task_id"],
                run_id="structured-run-789",
            ):
                pass

        self.assertEqual(self.changes.list_proposals(), [])

    async def test_rejects_prompt_over_model_context_budget(self):
        task = self.create_task()
        client = FakeTaskModelClient(
            plan=self.plan,
            change_set=self.generated,
            budget=10,
        )

        with self.assertRaisesRegex(ValueError, "safe budget"):
            async for _ in self.orchestrator(client).run_events(
                task_id=task["task_id"],
                run_id="structured-run-budget",
            ):
                pass

        failed = self.task_service.get_task(task["task_id"])
        self.assertEqual(failed["phase"], "planning_failed")


if __name__ == "__main__":
    unittest.main()
