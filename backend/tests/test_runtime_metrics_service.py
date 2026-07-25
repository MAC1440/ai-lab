import tempfile
import time
import unittest
from pathlib import Path

from services.runtime_metrics_service import RuntimeMetricsService


class RuntimeMetricsServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temp_dir.name) / "runtime-metrics.sqlite3"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _record(
        self,
        service: RuntimeMetricsService,
        *,
        stage: str,
        agent_id: str = "coding",
        model: str = "granite4.1:3b",
        input_tokens: int = 100,
        output_tokens: int = 25,
    ):
        started_at = time.perf_counter() - 2.0
        return service.record(
            started_at=started_at,
            agent_id=agent_id,
            stage=stage,
            runtime={
                "provider_id": "ollama",
                "model": model,
                "assignment_source": "agent",
            },
            usage={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            context_window=4096,
            max_tokens=1024,
            safe_input_tokens=2304,
            temperature=0.1,
        )

    def test_metrics_survive_service_restart(self):
        first = RuntimeMetricsService(
            database_path=self.database_path,
            history_size=100,
        )
        self._record(first, stage="chat")

        second = RuntimeMetricsService(
            database_path=self.database_path,
            history_size=100,
        )
        snapshot = second.snapshot()

        self.assertTrue(snapshot["persistent"])
        self.assertEqual(snapshot["summary"]["run_count"], 1)
        self.assertEqual(snapshot["latest"]["stage"], "chat")
        self.assertEqual(snapshot["latest"]["input_tokens"], 100)
        self.assertEqual(snapshot["latest"]["output_tokens"], 25)

    def test_snapshot_filters_by_stage_agent_and_model(self):
        service = RuntimeMetricsService(
            database_path=self.database_path,
            history_size=100,
        )
        self._record(service, stage="chat", agent_id="coding")
        self._record(
            service,
            stage="generation",
            agent_id="web",
            model="qwen3:4b",
        )
        self._record(service, stage="repair", agent_id="coding")

        snapshot = service.snapshot(
            stage="generation",
            agent_id="web",
            model="qwen3:4b",
        )

        self.assertEqual(snapshot["summary"]["run_count"], 1)
        self.assertEqual(snapshot["latest"]["stage"], "generation")
        self.assertEqual(snapshot["latest"]["agent_id"], "web")
        self.assertEqual(snapshot["latest"]["model"], "qwen3:4b")

    def test_history_is_trimmed_to_configured_size(self):
        service = RuntimeMetricsService(
            database_path=self.database_path,
            history_size=2,
        )
        self._record(service, stage="chat")
        self._record(service, stage="planning")
        self._record(service, stage="generation")

        snapshot = service.snapshot(limit=100)

        self.assertEqual(snapshot["summary"]["run_count"], 2)
        self.assertEqual(
            [item["stage"] for item in snapshot["history"]],
            ["generation", "planning"],
        )

    def test_clear_removes_persistent_history(self):
        service = RuntimeMetricsService(
            database_path=self.database_path,
            history_size=100,
        )
        self._record(service, stage="chat")
        self._record(service, stage="planning")

        removed = service.clear()

        self.assertEqual(removed, 2)
        self.assertEqual(service.snapshot()["history"], [])


if __name__ == "__main__":
    unittest.main()
