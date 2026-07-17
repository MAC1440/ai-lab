import tempfile
import unittest
from pathlib import Path

from services.change_service import ChangeService
from services.repair_service import RepairService, RepairTaskStateError
from services.repair_store import RepairStore


class FakeWorkspaceService:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def get_workspace(self):
        return self.root

    def resolve_workspace_path(self, relative_path="."):
        target = (self.root / relative_path).resolve()
        target.relative_to(self.root)
        return target


class FakeVerificationStore:
    def __init__(self, run):
        self.run = run

    def get_run(self, run_id):
        assert run_id == self.run["run_id"]
        return dict(self.run)


class RepairServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()
        self.workspace = FakeWorkspaceService(self.root)
        self.run = {
            "run_id": "run-1",
            "workspace": str(self.root),
            "profile_id": "python-tests",
            "profile_name": "Python tests",
            "display_command": "python -m pytest -q",
            "status": "failed",
            "output": "1 failed",
            "error": None,
        }
        self.changes = ChangeService(self.workspace)
        self.service = RepairService(
            workspace_service=self.workspace,
            verification_store=FakeVerificationStore(self.run),
            change_service=self.changes,
            store=RepairStore(self.root / "repairs.sqlite3"),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_failed_run_creates_repair_task(self):
        result = self.service.create_from_verification("run-1")
        self.assertEqual(result["status"], "open")
        self.assertEqual(result["failure_excerpt"], "1 failed")

    def test_non_failed_run_is_rejected(self):
        self.run["status"] = "passed"
        with self.assertRaises(RepairTaskStateError):
            self.service.create_from_verification("run-1")

    def test_creation_is_idempotent_for_same_run(self):
        first = self.service.create_from_verification("run-1")
        second = self.service.create_from_verification("run-1")
        self.assertEqual(first["task_id"], second["task_id"])

    def test_pending_proposal_moves_task_to_awaiting_review(self):
        repair = self.service.create_from_verification("run-1")
        self.changes.propose(
            file_path="fix.py",
            content="fixed = True\n",
            repair_task_id=repair["task_id"],
        )
        refreshed = self.service.get_task(repair["task_id"])
        self.assertEqual(refreshed["status"], "awaiting_review")

    def test_passed_verification_resolves_task(self):
        repair = self.service.create_from_verification("run-1")
        follow_up = dict(self.run, run_id="run-2", status="passed")
        result = self.service.record_verification(repair["task_id"], follow_up)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["latest_run_id"], "run-2")


if __name__ == "__main__":
    unittest.main()
