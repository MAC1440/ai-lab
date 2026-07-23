import tempfile
import unittest
from pathlib import Path

from services.reliability_benchmark_store import (
    ReliabilityBenchmarkRunNotFoundError,
    ReliabilityBenchmarkStore,
)


class ReliabilityBenchmarkStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "reliability.sqlite3"
        self.store = ReliabilityBenchmarkStore(self.database_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_persists_run_and_ordered_scenario_results(self):
        self.store.create_run(
            {
                "run_id": "run-12345678",
                "suite": "quick",
                "agent_override": None,
                "repetitions": 1,
                "started_at": "2026-07-23T00:00:00+00:00",
                "scenario_count": 1,
            }
        )
        self.store.add_result(
            "run-12345678",
            sequence=1,
            result={
                "scenario_id": "python_discount",
                "repetition": 1,
                "category": "workflow",
                "project_type": "python",
                "agent_id": "coding",
                "status": "passed",
                "duration_ms": 10,
                "score": 1.0,
                "assertions": [
                    {"name": "works", "passed": True, "detail": "ok"}
                ],
                "metrics": {"model_calls": 2},
                "error": None,
                "created_at": "2026-07-23T00:00:01+00:00",
            },
        )
        self.store.finish_run(
            "run-12345678",
            status="passed",
            finished_at="2026-07-23T00:00:02+00:00",
            duration_ms=2000,
            passed_count=1,
            failed_count=0,
            pass_rate=1.0,
        )

        restarted = ReliabilityBenchmarkStore(self.database_path)
        run = restarted.get_run("run-12345678")

        self.assertEqual(run["status"], "passed")
        self.assertEqual(run["results"][0]["scenario_id"], "python_discount")
        self.assertEqual(run["results"][0]["metrics"]["model_calls"], 2)
        self.assertEqual(restarted.list_runs()[0]["run_id"], "run-12345678")

    def test_restart_marks_running_run_interrupted(self):
        self.store.create_run(
            {
                "run_id": "run-interrupted",
                "suite": "full",
                "agent_override": "coding",
                "repetitions": 2,
                "started_at": "2026-07-23T00:00:00+00:00",
                "scenario_count": 14,
            }
        )

        restarted = ReliabilityBenchmarkStore(self.database_path)
        run = restarted.get_run("run-interrupted")

        self.assertEqual(run["status"], "interrupted")
        self.assertIn("backend stopped", run["error"].lower())

    def test_unknown_run_is_rejected(self):
        with self.assertRaises(ReliabilityBenchmarkRunNotFoundError):
            self.store.get_run("missing-run")


if __name__ == "__main__":
    unittest.main()
