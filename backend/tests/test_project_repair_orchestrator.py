import tempfile
import unittest
from pathlib import Path
from typing import Type

from pydantic import BaseModel

from services.change_service import ChangeService
from services.project_repair_orchestrator import ProjectRepairOrchestrator
from services.project_task_service import ProjectTaskService
from services.project_task_store import ProjectTaskStore
from services.source_validation_service import SourceValidationService
from services.task_context_service import GeneratedChangeSet
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


class FakeRepairService:
    def __init__(self):
        self.started = []

    def start_agent_attempt(self, task_id):
        self.started.append(task_id)
        return {"task_id": task_id}


class FakeVerificationStore:
    def get_run(self, run_id):
        return {
            "run_id": run_id,
            "status": "failed",
            "output": "AssertionError: expected 4 but received -2",
            "error": None,
        }


class FakeModelClient:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def prompt_budget(self, *, agent_id, stage):
        return 100_000

    def estimate_tokens(self, *, agent_id, stage, text):
        return len(text)

    async def generate(
        self,
        *,
        agent_id: str,
        stage: str,
        prompt: str,
        output_type: Type[BaseModel],
    ):
        self.calls.append((agent_id, stage, prompt))
        return ModelStageResult(
            output=output_type.model_validate(self.output.model_dump()),
            usage={"requests": 1},
            model="repair-model",
            provider_id="test",
            capability={"profile_source": "saved"},
        )


class ProjectRepairOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "calculator.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a - b\n",
            encoding="utf-8",
        )
        self.workspace = TemporaryWorkspaceService(self.root)
        self.changes = ChangeService(self.workspace)
        self.tasks = ProjectTaskService(
            workspace_service=self.workspace,
            change_service=self.changes,
            store=ProjectTaskStore(self.root / "tasks.sqlite3"),
        )
        task = self.tasks.create(
            title="Fix calculator",
            goal="Make add return the sum.",
            agent_id="coding",
            max_attempts=3,
        )
        proposals = self.changes.propose_change_set(
            operations=[
                {
                    "path": "src/calculator.py",
                    "operation": "update",
                    "summary": "Introduce the broken implementation.",
                    "content": (
                        "def add(a: int, b: int) -> int:\n"
                        "    return a - b  # broken\n"
                    ),
                }
            ],
            change_set_id="original-set",
        )
        self.changes.approve_change_set("original-set")
        self.task_id = task["task_id"]
        self.tasks.store.update(
            self.task_id,
            status="needs_attention",
            phase="repairing",
            current_change_set_id="original-set",
            latest_verification_run_id="verify-1",
            repair_task_id="repair-1",
            updated_at=self.tasks._utc_now(),
        )
        self.assertEqual(proposals[0]["status"], "pending")

    def tearDown(self):
        self.temp_dir.cleanup()

    def generated(self, path="src/calculator.py"):
        return GeneratedChangeSet.model_validate(
            {
                "summary": "Repair calculator.",
                "operations": [
                    {
                        "path": path,
                        "operation": "update",
                        "summary": "Return the sum.",
                        "content": (
                            "def add(a: int, b: int) -> int:\n"
                            "    return a + b\n"
                        ),
                    }
                ],
            }
        )

    def orchestrator(self, generated):
        return ProjectRepairOrchestrator(
            task_service=self.tasks,
            change_service=self.changes,
            repair_service=FakeRepairService(),
            verification_store=FakeVerificationStore(),
            model_client=FakeModelClient(generated),
            source_validation_service=SourceValidationService(self.workspace),
        )

    async def test_generates_reviewable_bounded_repair(self):
        events = [
            event
            async for event in self.orchestrator(self.generated()).run_events(
                task_id=self.task_id,
                run_id="repair-run-1",
            )
        ]

        self.assertEqual(events[-2]["type"], "repair_change_set")
        self.assertEqual(events[-1]["task"]["status"], "awaiting_approval")
        self.assertIn("return a + b", events[-2]["proposals"][0]["diff"])

    def test_path_validation_accepts_windows_and_posix_separators(self):
        ProjectRepairOrchestrator._validate_output(
            self.generated("src/calculator.py"),
            ["src\\calculator.py"],
        )

    async def test_rejects_unrelated_repair_path_without_proposal(self):
        with self.assertRaisesRegex(ValueError, "unrelated"):
            async for _ in self.orchestrator(
                self.generated("src/unrelated.py")
            ).run_events(task_id=self.task_id, run_id="repair-run-2"):
                pass

        proposals = self.changes.list_proposals(
            repair_task_id="repair-1"
        )
        self.assertEqual(proposals, [])


if __name__ == "__main__":
    unittest.main()
