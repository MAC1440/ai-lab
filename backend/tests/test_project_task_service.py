import tempfile
import unittest
from pathlib import Path

from services.change_service import ChangeService
from services.project_task_service import (
    ProjectTaskService,
    ProjectTaskStateError,
)
from services.project_task_store import ProjectTaskStore


class TemporaryWorkspaceService:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def get_workspace(self) -> Path:
        return self.root

    def resolve_workspace_path(self, relative_path: str) -> Path:
        target = (self.root / relative_path).resolve()
        target.relative_to(self.root)
        return target


class ProjectTaskServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.workspace = TemporaryWorkspaceService(self.root)
        self.changes = ChangeService(self.workspace)
        self.store = ProjectTaskStore(self.root / "tasks.sqlite3")
        self.service = ProjectTaskService(
            workspace_service=self.workspace,
            change_service=self.changes,
            store=self.store,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_full_task_requires_approval_then_verification(self):
        task = self.service.create(
            title="Add player health",
            goal="Create a health component and tests.",
            agent_id="unity",
        )
        self.service.start_agent_run(task["task_id"], "agent-run-123")
        self.changes.propose(
            file_path="Assets/Health.cs",
            content="public class Health {}\n",
            change_set_id="set-123",
        )

        proposed = self.service.record_agent_result(
            task["task_id"],
            run_id="agent-run-123",
            result={"change_set_id": "set-123"},
        )
        self.assertEqual(proposed["status"], "awaiting_approval")
        self.assertFalse((self.root / "Assets" / "Health.cs").exists())

        self.changes.approve_change_set("set-123")
        ready = self.service.get_task(task["task_id"])
        self.assertEqual(ready["status"], "ready_to_verify")
        self.assertTrue((self.root / "Assets" / "Health.cs").is_file())

        self.service.record_verification_started(
            task["task_id"],
            run_id="verify-run-123",
            profile_id="unity-compile",
        )
        completed = self.service.record_verification_result(
            task["task_id"],
            run={
                "run_id": "verify-run-123",
                "workspace": str(self.root.resolve()),
                "status": "passed",
            },
        )
        self.assertEqual(completed["status"], "completed")
        self.assertIsNotNone(completed["completed_at"])

    def test_agent_without_proposals_pauses_for_attention(self):
        task = self.service.create(
            title="Explain only",
            goal="This must still produce changes.",
            agent_id="coding",
        )
        self.service.start_agent_run(task["task_id"], "agent-run-456")

        result = self.service.record_agent_result(
            task["task_id"],
            run_id="agent-run-456",
            result={"change_set_id": "empty-set"},
        )

        self.assertEqual(result["status"], "needs_attention")
        self.assertTrue(result["can_resume"])

    def test_execution_prompt_describes_the_strict_change_set_contract(self):
        task = self.service.create(
            title="Authentication page",
            goal="Add login and signup pages.",
            agent_id="web",
        )

        prompt = task["execution_prompt"]

        self.assertIn("file_path and new_text", prompt)
        self.assertIn("Do not send an operation field", prompt)
        self.assertIn("exactly once", prompt)
        self.assertIn("normally no more than 8 files", prompt)

    def test_cancelled_task_cannot_restart(self):
        task = self.service.create(
            title="Cancelled work",
            goal="Do not execute after cancellation.",
            agent_id="unity",
        )
        self.service.cancel(task["task_id"])

        with self.assertRaises(ProjectTaskStateError):
            self.service.start_agent_run(task["task_id"], "agent-run-789")

    def test_store_marks_active_task_paused_after_restart(self):
        task = self.service.create(
            title="Interrupted work",
            goal="Resume safely after restart.",
            agent_id="unity",
        )
        self.service.start_agent_run(task["task_id"], "agent-run-active")

        restarted_store = ProjectTaskStore(self.root / "tasks.sqlite3")
        restarted = restarted_store.get(task["task_id"])

        self.assertEqual(restarted["status"], "paused")
        self.assertEqual(restarted["phase"], "interrupted")
        self.assertIsNone(restarted["current_agent_run_id"])


if __name__ == "__main__":
    unittest.main()
