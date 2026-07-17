import tempfile
import unittest
from pathlib import Path

from services.repair_store import RepairStore, RepairTaskNotFoundError


def task(task_id="task-1", workspace="/workspace"):
    return {
        "task_id": task_id,
        "workspace": workspace,
        "title": "Repair tests",
        "status": "open",
        "source_run_id": f"run-{task_id}",
        "latest_run_id": f"run-{task_id}",
        "profile_id": "python-tests",
        "profile_name": "Python tests",
        "display_command": "python -m pytest -q",
        "failure_excerpt": "1 failed",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "resolved_at": None,
    }


class RepairStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = RepairStore(Path(self.temp_dir.name) / "repairs.sqlite3")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_get_and_find_by_source_run(self):
        created = self.store.create(task())
        self.assertEqual(self.store.get(created["task_id"])["status"], "open")
        self.assertEqual(
            self.store.find_by_source_run("run-task-1")["task_id"],
            "task-1",
        )

    def test_list_is_scoped_to_workspace(self):
        self.store.create(task("one", "/one"))
        self.store.create(task("two", "/two"))
        results = self.store.list(workspace="/one")
        self.assertEqual([item["task_id"] for item in results], ["one"])

    def test_update_persists_status_and_latest_run(self):
        self.store.create(task())
        updated = self.store.update(
            "task-1",
            status="passed",
            updated_at="2026-01-02T00:00:00+00:00",
            latest_run_id="run-2",
            resolved_at="2026-01-02T00:00:00+00:00",
        )
        self.assertEqual(updated["status"], "passed")
        self.assertEqual(updated["latest_run_id"], "run-2")

    def test_unknown_task_raises(self):
        with self.assertRaises(RepairTaskNotFoundError):
            self.store.get("missing")


if __name__ == "__main__":
    unittest.main()
