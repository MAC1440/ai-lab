import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic_ai import Agent
from pydantic_ai.models.function import FunctionModel

from services.agent_service import AgentService
from services.model_capability_service import ModelCapabilityService
from services.pydantic_agent import AgentRunDeps
from services.pydantic_runner import PydanticAgentRunner
from services.runtime_settings_service import (
    RuntimeSettingsDocument,
    RuntimeSettingsService,
    RuntimeStageSettings,
)
from services.task_model_client import PydanticTaskModelClient


class FakeProviderSettings:
    def runtime_config(self, agent_id, fallback_model, *, stage=None):
        del agent_id, fallback_model, stage
        return {
            "provider_id": "ollama",
            "model": "test-model",
            "provider": {
                "kind": "ollama",
                "base_url": "http://localhost:11434",
            },
            "generation": {
                "temperature": 0.1,
                "max_tokens": 4096,
                "context_window": 16384,
            },
        }


class RecordingMetricsService:
    def __init__(self):
        self.calls = []

    @staticmethod
    def timer():
        import time
        return time.perf_counter()

    def record(self, **kwargs):
        self.calls.append(kwargs)
        usage = kwargs["usage"]
        return {
            "recorded_at": "2026-07-25T00:00:00+00:00",
            "agent_id": kwargs["agent_id"],
            "stage": kwargs["stage"],
            "provider_id": kwargs["runtime"]["provider_id"],
            "model": kwargs["runtime"]["model"],
            "duration_seconds": 1.0,
            "input_tokens": int(usage.get("input_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
            "tokens_per_second": 5.0,
            "prompt_tokens_per_second": None,
            "context_window": kwargs["context_window"],
            "max_tokens": kwargs["max_tokens"],
            "safe_input_tokens": kwargs["safe_input_tokens"],
            "context_used_tokens": int(usage.get("input_tokens") or 0),
            "context_remaining_tokens": max(
                0,
                kwargs["context_window"]
                - int(usage.get("input_tokens") or 0),
            ),
            "temperature": kwargs["temperature"],
            "assignment_source": "agent",
        }


class RuntimeStabilizationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.runtime_settings = RuntimeSettingsService(
            root / "runtime-settings.json"
        )
        document = self.runtime_settings.get()
        document.automatic = False
        document.planning = RuntimeStageSettings(
            num_ctx=4096,
            max_tokens=1024,
            reserve_tokens=768,
            temperature=0.0,
        )
        document.chat = RuntimeStageSettings(
            num_ctx=4096,
            max_tokens=1024,
            reserve_tokens=768,
            temperature=0.1,
        )
        self.runtime_settings.save(document)
        self.capabilities = ModelCapabilityService(
            root / "capabilities.json"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_prompt_budget_respects_runtime_stage_limit(self):
        client = PydanticTaskModelClient(
            provider_settings_service=FakeProviderSettings(),
            model_capability_service=self.capabilities,
            agent_service=AgentService(),
            runtime_settings_service=self.runtime_settings,
        )

        self.assertEqual(
            client.prompt_budget(agent_id="coding", stage="planning"),
            2304,
        )

    async def test_chat_preserves_repair_id_and_emits_truthful_metrics(self):
        async def model_stream(messages, info):
            del messages, info
            yield "A response long enough to create a completed run."

        agent = Agent(
            model=FunctionModel(stream_function=model_stream),
            deps_type=AgentRunDeps,
        )
        metrics = RecordingMetricsService()

        with patch(
            "services.pydantic_runner.get_pydantic_agent",
            return_value=agent,
        ):
            events = [
                event
                async for event in PydanticAgentRunner(
                    provider_settings_service=FakeProviderSettings(),
                    runtime_settings_service=self.runtime_settings,
                    runtime_metrics_service=metrics,
                ).run_events(
                    agent_id="coding",
                    prompt="Repair the task",
                    repair_task_id="repair-123",
                )
            ]

        final_metric = next(
            event for event in events
            if event["type"] == "metrics"
            and event["metrics"]["final"]
        )
        done = events[-1]

        self.assertEqual(final_metric["metrics"]["metric_kind"], "measured")
        self.assertEqual(done["type"], "done")
        self.assertEqual(done["result"]["repair_task_id"], "repair-123")
        self.assertIsNotNone(done["result"]["runtime_metric"])
        self.assertEqual(metrics.calls[0]["stage"], "chat")
        self.assertEqual(metrics.calls[0]["safe_input_tokens"], 2304)


if __name__ == "__main__":
    unittest.main()
