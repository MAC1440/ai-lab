import tempfile
import unittest
from pathlib import Path

from services.model_benchmark_service import ModelBenchmarkService
from services.model_capability_service import ModelCapabilityService
from services.task_context_service import GeneratedChangeSet, ImplementationPlan
from services.task_model_client import ModelStageResult


class FakeBenchmarkModelClient:
    async def generate(self, *, agent_id, stage, prompt, output_type):
        del agent_id, prompt
        if stage == "planning":
            output = ImplementationPlan.model_validate(
                {
                    "summary": "Create greeting and connect it.",
                    "files": [
                        {
                            "path": "src/existing.py",
                            "operation": "update",
                            "reason": "Import and use greet.",
                        },
                        {
                            "path": "src/greeting.py",
                            "operation": "create",
                            "reason": "Implement greet.",
                        },
                    ],
                    "verification": ["python-tests"],
                }
            )
        elif stage == "generation":
            output = GeneratedChangeSet.model_validate(
                {
                    "summary": "Implement greeting.",
                    "operations": [
                        {
                            "path": "src/existing.py",
                            "operation": "update",
                            "summary": "Use greet.",
                            "content": (
                                "from src.greeting import greet\n"
                                'message = greet("Mac")\n'
                            ),
                        },
                        {
                            "path": "src/greeting.py",
                            "operation": "create",
                            "summary": "Add greet.",
                            "content": (
                                "def greet(name: str) -> str:\n"
                                '    return f"Hello, {name}"\n'
                            ),
                        },
                    ],
                }
            )
        else:
            output = GeneratedChangeSet.model_validate(
                {
                    "summary": "Repair addition.",
                    "operations": [
                        {
                            "path": "src/calculator.py",
                            "operation": "update",
                            "summary": "Add values.",
                            "content": (
                                "def add(a: int, b: int) -> int:\n"
                                "    return a + b\n"
                            ),
                        }
                    ],
                }
            )
        return ModelStageResult(
            output=output_type.model_validate(output.model_dump()),
            usage={"output_tokens": 100},
            model="benchmark-model",
            provider_id="local",
            capability={
                "provider_id": "local",
                "model": "benchmark-model",
                "context_window": 8192,
                "effective_context_window": 8192,
                "effective_safe_input_tokens": 6000,
                "max_output_tokens": 2048,
                "effective_max_output_tokens": 2048,
                "structured_output_mode": "native",
                "supports_tools": True,
                "supports_parallel_tools": False,
                "estimated_characters_per_token": 3.0,
            },
        )


class ModelBenchmarkServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_records_stage_scores_and_recommendations(self):
        with tempfile.TemporaryDirectory() as directory:
            capabilities = ModelCapabilityService(
                Path(directory) / "capabilities.json"
            )
            service = ModelBenchmarkService(
                model_client=FakeBenchmarkModelClient(),
                capability_service=capabilities,
            )

            events = [
                event
                async for event in service.run_events(agent_id="coding")
            ]

            self.assertEqual(events[0]["type"], "benchmark_started")
            self.assertEqual(events[-1]["type"], "benchmark_done")
            self.assertEqual(
                [item["score"] for item in events[-1]["results"]],
                [1.0, 1.0, 1.0],
            )
            profile = capabilities.get_profile(
                "local",
                "benchmark-model",
            )
            self.assertEqual(
                profile["stage_scores"],
                {"planning": 1.0, "generation": 1.0, "repair": 1.0},
            )
            recommendations = capabilities.recommend_assignments()
            self.assertEqual(
                recommendations["recommendations"]["generation"]["model"],
                "benchmark-model",
            )
            self.assertFalse(recommendations["applied"])


if __name__ == "__main__":
    unittest.main()
