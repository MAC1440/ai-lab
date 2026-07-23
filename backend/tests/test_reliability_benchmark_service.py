import tempfile
import unittest
from pathlib import Path

from pydantic import BaseModel

from services.reliability_benchmark_service import (
    ReliabilityBenchmarkService,
)
from services.reliability_benchmark_store import ReliabilityBenchmarkStore
from services.task_context_service import (
    GeneratedChangeSet,
    ImplementationPlan,
)
from services.task_model_client import ModelStageResult


class FakeReliabilityModelClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def prompt_budget(self, *, agent_id: str, stage: str) -> int:
        del agent_id, stage
        return 200_000

    def estimate_tokens(
        self,
        *,
        agent_id: str,
        stage: str,
        text: str,
    ) -> int:
        del agent_id, stage
        return len(text) // 3

    async def generate(
        self,
        *,
        agent_id: str,
        stage: str,
        prompt: str,
        output_type: type[BaseModel],
    ) -> ModelStageResult:
        self.calls.append((agent_id, stage))
        if "discounted_price" in prompt:
            output = self._python(stage)
        elif "status-card.tsx" in prompt:
            output = self._nextjs(stage)
        elif "DamageInfo.cs" in prompt:
            output = self._unity(stage)
        else:
            raise AssertionError("Unknown reliability fixture prompt")
        return ModelStageResult(
            output=output_type.model_validate(output.model_dump()),
            usage={
                "requests": 1,
                "input_tokens": 100,
                "output_tokens": 50,
            },
            model="fixture-coder",
            provider_id="test",
            capability={"profile_source": "test"},
        )

    @staticmethod
    def _python(stage: str) -> BaseModel:
        if stage == "planning":
            return ImplementationPlan.model_validate(
                {
                    "summary": "Implement discount validation.",
                    "files": [
                        {
                            "path": "src/pricing.py",
                            "operation": "update",
                            "reason": "Correct discount behavior.",
                        }
                    ],
                    "verification": ["python tests"],
                }
            )
        return GeneratedChangeSet.model_validate(
            {
                "summary": "Implement discount validation.",
                "operations": [
                    {
                        "path": "src/pricing.py",
                        "operation": "update",
                        "summary": "Validate and apply the percentage.",
                        "content": (
                            "def discounted_price(\n"
                            "    total: float,\n"
                            "    percent: float,\n"
                            ") -> float:\n"
                            "    if not 0 <= percent <= 100:\n"
                            '        raise ValueError("percent out of range")\n'
                            "    return total * (1 - percent / 100)\n"
                        ),
                    }
                ],
            }
        )

    @staticmethod
    def _nextjs(stage: str) -> BaseModel:
        if stage == "planning":
            return ImplementationPlan.model_validate(
                {
                    "summary": "Add the status card.",
                    "files": [
                        {
                            "path": "src/app/page.tsx",
                            "operation": "update",
                            "reason": "Render the card.",
                        },
                        {
                            "path": "src/components/status-card.tsx",
                            "operation": "create",
                            "reason": "Add the typed component.",
                        },
                    ],
                    "verification": ["typescript"],
                }
            )
        return GeneratedChangeSet.model_validate(
            {
                "summary": "Add the status card.",
                "operations": [
                    {
                        "path": "src/app/page.tsx",
                        "operation": "update",
                        "summary": "Render StatusCard.",
                        "content": (
                            'import { StatusCard } from "../components/'
                            'status-card";\n\n'
                            "export default function Page() {\n"
                            '  return <StatusCard title="Workspace" '
                            'status="Ready" />;\n'
                            "}\n"
                        ),
                    },
                    {
                        "path": "src/components/status-card.tsx",
                        "operation": "create",
                        "summary": "Create StatusCard.",
                        "content": (
                            "type StatusCardProps = {\n"
                            "  title: string;\n"
                            "  status: string;\n"
                            "};\n\n"
                            "export function StatusCard({ title, status }: "
                            "StatusCardProps) {\n"
                            "  return <section><h2>{title}</h2>"
                            "<p>{status}</p></section>;\n"
                            "}\n"
                        ),
                    },
                ],
            }
        )

    @staticmethod
    def _unity(stage: str) -> BaseModel:
        if stage == "planning":
            return ImplementationPlan.model_validate(
                {
                    "summary": "Add typed damage input.",
                    "files": [
                        {
                            "path": "Assets/Scripts/DamageInfo.cs",
                            "operation": "create",
                            "reason": "Represent damage data.",
                        },
                        {
                            "path": "Assets/Scripts/PlayerHealth.cs",
                            "operation": "update",
                            "reason": "Consume DamageInfo.",
                        },
                    ],
                    "verification": ["unity compile"],
                }
            )
        return GeneratedChangeSet.model_validate(
            {
                "summary": "Add typed damage input.",
                "operations": [
                    {
                        "path": "Assets/Scripts/DamageInfo.cs",
                        "operation": "create",
                        "summary": "Create damage value.",
                        "content": (
                            "using UnityEngine;\n\n"
                            "public readonly struct DamageInfo\n"
                            "{\n"
                            "    public readonly int Amount;\n"
                            "    public readonly GameObject Source;\n\n"
                            "    public DamageInfo(int amount, GameObject source)\n"
                            "    {\n"
                            "        Amount = amount;\n"
                            "        Source = source;\n"
                            "    }\n"
                            "}\n"
                        ),
                    },
                    {
                        "path": "Assets/Scripts/PlayerHealth.cs",
                        "operation": "update",
                        "summary": "Apply bounded damage.",
                        "content": (
                            "using UnityEngine;\n\n"
                            "public class PlayerHealth : MonoBehaviour\n"
                            "{\n"
                            "    [SerializeField] private int maxHealth = 100;\n"
                            "    private int currentHealth;\n\n"
                            "    public void ApplyDamage(DamageInfo damage)\n"
                            "    {\n"
                            "        currentHealth = Mathf.Max(0, "
                            "currentHealth - damage.Amount);\n"
                            "    }\n"
                            "}\n"
                        ),
                    },
                ],
            }
        )


class ReliabilityBenchmarkServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.model = FakeReliabilityModelClient()
        self.store = ReliabilityBenchmarkStore(
            self.root / "reliability.sqlite3"
        )
        self.service = ReliabilityBenchmarkService(
            model_client=self.model,
            store=self.store,
            work_root=self.root / "workspaces",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    async def test_quick_suite_uses_real_workflow_and_safety_guards(self):
        events = [
            event
            async for event in self.service.run_events(
                suite="quick",
                repetitions=1,
            )
        ]

        self.assertEqual(events[0]["type"], "reliability_started")
        self.assertEqual(events[-1]["type"], "reliability_done")
        run = events[-1]["run"]
        self.assertEqual(run["status"], "passed")
        self.assertEqual(run["passed_count"], 3)
        self.assertEqual(run["pass_rate"], 1.0)
        self.assertEqual(
            self.model.calls,
            [("coding", "planning"), ("coding", "generation")],
        )
        stored = self.store.get_run(run["run_id"])
        self.assertEqual(len(stored["results"]), 3)
        self.assertFalse(any((self.root / "workspaces").iterdir()))

    async def test_full_suite_uses_project_specific_agent_assignments(self):
        events = [
            event
            async for event in self.service.run_events(
                suite="full",
                repetitions=1,
            )
        ]

        run = events[-1]["run"]
        self.assertEqual(run["status"], "passed")
        self.assertEqual(run["scenario_count"], 7)
        self.assertEqual(
            self.model.calls,
            [
                ("coding", "planning"),
                ("coding", "generation"),
                ("web", "planning"),
                ("web", "generation"),
                ("unity", "planning"),
                ("unity", "generation"),
            ],
        )

    async def test_agent_override_forces_one_assignment(self):
        events = [
            event
            async for event in self.service.run_events(
                suite="full",
                repetitions=1,
                agent_override="coding",
            )
        ]

        self.assertEqual(events[-1]["run"]["status"], "passed")
        self.assertTrue(all(agent == "coding" for agent, _ in self.model.calls))

    def test_scenario_catalog_marks_model_call_cost(self):
        scenarios = self.service.list_scenarios()
        python = next(
            item for item in scenarios if item["scenario_id"] == "python_discount"
        )
        rollback = next(
            item
            for item in scenarios
            if item["scenario_id"] == "transaction_rollback"
        )

        self.assertEqual(python["model_calls"], 2)
        self.assertEqual(rollback["model_calls"], 0)


if __name__ == "__main__":
    unittest.main()
