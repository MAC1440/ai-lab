import sys
import types
import unittest
from unittest.mock import patch

from pydantic import BaseModel

from services.task_model_client import (
    PydanticTaskModelClient,
    TaskModelOutputError,
)
from services.model_capability_service import ModelCapabilityService
import tempfile
from pathlib import Path


class ExampleOutput(BaseModel):
    value: str


class FakeProviderSettingsService:
    def __init__(self, kind: str = "ollama") -> None:
        self.kind = kind

    def runtime_config(self, agent_id: str, fallback_model: str, *, stage=None):
        del agent_id, fallback_model, stage
        return {
            "provider_id": "test-provider",
            "model": "test-model",
            "provider": {"kind": self.kind},
            "generation": {
                "temperature": 0.9,
                "max_tokens": 1024,
                "context_window": 8192,
            },
        }


class FakeAgentService:
    def get_agent(self, agent_id: str):
        return {
            "id": agent_id,
            "model": "fallback",
            "system_prompt": "Be careful.",
        }


class FakeUsage:
    requests = 1
    input_tokens = 10
    output_tokens = 5
    tool_calls = 0


class FakeResult:
    output = ExampleOutput(value="ok")
    usage = FakeUsage()


class FakeNativeOutput:
    def __init__(self, output_type, *, name: str, description: str) -> None:
        self.output_type = output_type
        self.name = name
        self.description = description


class FakeUnexpectedModelBehavior(RuntimeError):
    pass


class TaskModelClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.capabilities = ModelCapabilityService(
            Path(self.temp_dir.name) / "capabilities.json"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _fake_modules(self, agent_type):
        pydantic_ai = types.ModuleType("pydantic_ai")
        pydantic_ai.Agent = agent_type
        pydantic_ai.ModelSettings = lambda **kwargs: kwargs
        pydantic_ai.NativeOutput = FakeNativeOutput
        pydantic_ai.UnexpectedModelBehavior = FakeUnexpectedModelBehavior
        pydantic_ai.UsageLimits = lambda **kwargs: kwargs

        pydantic_model = types.ModuleType("services.pydantic_model")
        pydantic_model.build_pydantic_model = lambda runtime: object()
        return {
            "pydantic_ai": pydantic_ai,
            "services.pydantic_model": pydantic_model,
        }

    async def test_ollama_uses_native_json_schema_output(self):
        captured = {}

        class FakeAgent:
            def __init__(self, model, **kwargs):
                del model
                captured.update(kwargs)

            async def run(self, prompt, **kwargs):
                captured["prompt"] = prompt
                captured["run"] = kwargs
                return FakeResult()

        client = PydanticTaskModelClient(
            provider_settings_service=FakeProviderSettingsService("ollama"),
            model_capability_service=self.capabilities,
            agent_service=FakeAgentService(),
        )
        with patch.dict(
            sys.modules,
            self._fake_modules(FakeAgent),
        ):
            result = await client.generate(
                agent_id="unity",
                stage="planning",
                prompt="Plan it.",
                output_type=ExampleOutput,
            )

        self.assertEqual(result.output.value, "ok")
        self.assertIsInstance(captured["output_type"], FakeNativeOutput)
        self.assertIs(captured["output_type"].output_type, ExampleOutput)
        self.assertEqual(captured["run"]["model_settings"]["temperature"], 0.0)

    async def test_unknown_openai_compatible_provider_keeps_tool_output(self):
        captured = {}

        class FakeAgent:
            def __init__(self, model, **kwargs):
                del model
                captured.update(kwargs)

            async def run(self, prompt, **kwargs):
                del prompt, kwargs
                return FakeResult()

        client = PydanticTaskModelClient(
            provider_settings_service=FakeProviderSettingsService(
                "openai_compatible"
            ),
            model_capability_service=self.capabilities,
            agent_service=FakeAgentService(),
        )
        with patch.dict(
            sys.modules,
            self._fake_modules(FakeAgent),
        ):
            await client.generate(
                agent_id="coding",
                stage="generation",
                prompt="Generate it.",
                output_type=ExampleOutput,
            )

        self.assertIs(captured["output_type"], ExampleOutput)

    async def test_structured_output_failure_has_stage_and_model_context(self):
        class FailingAgent:
            def __init__(self, model, **kwargs):
                del model, kwargs

            async def run(self, prompt, **kwargs):
                del prompt, kwargs
                cause = ValueError("files.0.operation is required")
                raise FakeUnexpectedModelBehavior(
                    "Exceeded maximum output retries"
                ) from cause

        client = PydanticTaskModelClient(
            provider_settings_service=FakeProviderSettingsService("ollama"),
            model_capability_service=self.capabilities,
            agent_service=FakeAgentService(),
        )
        with patch.dict(
            sys.modules,
            self._fake_modules(FailingAgent),
        ):
            with self.assertRaises(TaskModelOutputError) as raised:
                await client.generate(
                    agent_id="unity",
                    stage="planning",
                    prompt="Plan it.",
                    output_type=ExampleOutput,
                )

        error = raised.exception
        self.assertEqual(error.stage, "planning")
        self.assertEqual(error.model, "test-model")
        self.assertIn("files.0.operation is required", str(error))

    def test_repair_stage_has_bounded_system_prompt(self):
        prompt = PydanticTaskModelClient._system_prompt(
            {"system_prompt": "Be careful."},
            "repair",
        )

        self.assertIn("smallest complete-file correction", prompt)
        self.assertIn("Do not call tools or touch unlisted files", prompt)


if __name__ == "__main__":
    unittest.main()
