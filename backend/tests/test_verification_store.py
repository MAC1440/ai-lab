import tempfile
import unittest
from pathlib import Path

from services.verification_store import (
    VerificationRunNotFoundError,
    VerificationStore,
)


class VerificationStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "verification.sqlite3"
        self.store = VerificationStore(self.database_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_persists_completed_run(self):
        self.store.create_run(
            run_id="run-1",
            workspace="C:/workspace",
            profile_id="python-tests",
            profile_name="Python tests",
            project_type="python",
            working_directory="backend",
            command=["python", "-m", "pytest", "-q"],
            display_command="python -m pytest -q",
            proposal_id="proposal-1",
            started_at="2026-01-01T00:00:00+00:00",
        )
        self.store.finish_run(
            "run-1",
            status="passed",
            finished_at="2026-01-01T00:00:02+00:00",
            duration_ms=2000,
            exit_code=0,
            output="4 passed\n",
            output_truncated=False,
            error=None,
        )

        reopened = VerificationStore(self.database_path)
        run = reopened.get_run("run-1")

        self.assertEqual(run["status"], "passed")
        self.assertEqual(run["exit_code"], 0)
        self.assertEqual(run["proposal_id"], "proposal-1")
        self.assertEqual(run["output"], "4 passed\n")

    def test_list_filters_by_workspace(self):
        for index, workspace in enumerate(("one", "two"), start=1):
            self.store.create_run(
                run_id=f"run-{index}",
                workspace=workspace,
                profile_id="profile",
                profile_name="Profile",
                project_type="python",
                working_directory=".",
                command=["python"],
                display_command="python",
                proposal_id=None,
                started_at=f"2026-01-01T00:00:0{index}+00:00",
            )

        runs = self.store.list_runs(workspace="two")

        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["run_id"], "run-2")
        self.assertNotIn("output", runs[0])

    def test_missing_run_raises(self):
        with self.assertRaises(VerificationRunNotFoundError):
            self.store.get_run("missing")


if __name__ == "__main__":
    unittest.main()
