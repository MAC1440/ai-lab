from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, Type
from uuid import uuid4

from pydantic import BaseModel

from services.model_capability_service import ModelCapabilityService
from services.task_context_service import GeneratedChangeSet, ImplementationPlan
from services.task_model_client import TaskModelClient


class ModelBenchmarkService:
    """Run small repeatable structured coding tests against assigned models."""

    def __init__(
        self,
        *,
        model_client: TaskModelClient,
        capability_service: ModelCapabilityService,
    ) -> None:
        self.model_client = model_client
        self.capability_service = capability_service

    async def run_events(
        self,
        *,
        agent_id: str,
    ) -> AsyncIterator[Dict[str, Any]]:
        benchmark_id = uuid4().hex
        results: list[Dict[str, Any]] = []
        yield {
            "type": "benchmark_started",
            "benchmark_id": benchmark_id,
            "agent_id": agent_id,
            "stages": ["planning", "generation", "repair"],
        }
        for stage in ("planning", "generation", "repair"):
            yield {
                "type": "benchmark_stage_started",
                "benchmark_id": benchmark_id,
                "stage": stage,
            }
            output_type, prompt = self._fixture(stage)
            started = time.monotonic()
            try:
                result = await self.model_client.generate(
                    agent_id=agent_id,
                    stage=stage,
                    prompt=prompt,
                    output_type=output_type,
                )
                duration_seconds = max(0.001, time.monotonic() - started)
                score, assertions = self._score(stage, result.output)
                output_tokens = int(result.usage.get("output_tokens") or 0)
                tokens_per_second = (
                    output_tokens / duration_seconds if output_tokens > 0 else None
                )
                measured_at = self._utc_now()
                profile = self.capability_service.record_benchmark(
                    capability=result.capability,
                    stage=stage,
                    score=score,
                    measured_tokens_per_second=tokens_per_second,
                    benchmarked_at=measured_at,
                )
                stage_result = {
                    "stage": stage,
                    "status": "passed" if score >= 0.75 else "failed",
                    "score": score,
                    "assertions": assertions,
                    "duration_ms": round(duration_seconds * 1000),
                    "tokens_per_second": (
                        round(tokens_per_second, 3)
                        if tokens_per_second is not None
                        else None
                    ),
                    "model": result.model,
                    "provider_id": result.provider_id,
                    "usage": result.usage,
                    "capability_profile": profile,
                }
            except Exception as error:
                stage_result = {
                    "stage": stage,
                    "status": "error",
                    "score": 0.0,
                    "assertions": [],
                    "duration_ms": round((time.monotonic() - started) * 1000),
                    "error": str(error),
                }
            results.append(stage_result)
            yield {
                "type": "benchmark_stage_done",
                "benchmark_id": benchmark_id,
                "result": stage_result,
            }
        yield {
            "type": "benchmark_done",
            "benchmark_id": benchmark_id,
            "agent_id": agent_id,
            "results": results,
            "recommendations": self.capability_service.recommend_assignments(),
        }

    @staticmethod
    def _fixture(stage: str) -> tuple[Type[BaseModel], str]:
        if stage == "planning":
            return (
                ImplementationPlan,
                """
Return a structured implementation plan only.
Goal: update src/existing.py so it imports greet from src/greeting.py, and
create src/greeting.py containing the greet function.
Use exactly these two files. Mark src/existing.py as update and
src/greeting.py as create. Request python-tests verification.
""".strip(),
            )
        if stage == "generation":
            return (
                GeneratedChangeSet,
                """
Return a structured complete-file change set only, with exactly two operations:
1. update src/existing.py to this exact content:
from src.greeting import greet
message = greet("Mac")
2. create src/greeting.py with a typed greet(name: str) function returning
f"Hello, {name}".
Do not add other files.
""".strip(),
            )
        if stage == "repair":
            return (
                GeneratedChangeSet,
                """
Return a structured repair change set only.
The failing check says src/calculator.py subtracts instead of adds.
Return exactly one update operation for src/calculator.py with complete content
def add(a: int, b: int) -> int:
    return a + b
Do not add, delete, move, or mention other files.
""".strip(),
            )
        raise ValueError(f"Unknown benchmark stage: {stage}")

    @staticmethod
    def _score(
        stage: str,
        output: BaseModel,
    ) -> tuple[float, list[Dict[str, Any]]]:
        checks: list[tuple[str, bool]]
        if stage == "planning":
            plan = ImplementationPlan.model_validate(output)
            mapping = {item.path: item.operation for item in plan.files}
            checks = [
                ("exact_file_count", len(plan.files) == 2),
                ("existing_is_update", mapping.get("src/existing.py") == "update"),
                ("greeting_is_create", mapping.get("src/greeting.py") == "create"),
                (
                    "verification_requested",
                    any("python" in item.lower() for item in plan.verification),
                ),
            ]
        else:
            change_set = GeneratedChangeSet.model_validate(output)
            mapping = {item.path: item for item in change_set.operations}
            if stage == "generation":
                existing = mapping.get("src/existing.py")
                greeting = mapping.get("src/greeting.py")
                checks = [
                    ("exact_file_count", len(change_set.operations) == 2),
                    (
                        "existing_is_update",
                        existing is not None and existing.operation == "update",
                    ),
                    (
                        "greeting_is_create",
                        greeting is not None and greeting.operation == "create",
                    ),
                    (
                        "import_present",
                        existing is not None
                        and "from src.greeting import greet"
                        in (existing.content or ""),
                    ),
                    (
                        "typed_function",
                        greeting is not None
                        and "def greet(name: str)" in (greeting.content or ""),
                    ),
                ]
            else:
                repair = mapping.get("src/calculator.py")
                checks = [
                    ("exact_file_count", len(change_set.operations) == 1),
                    (
                        "calculator_is_update",
                        repair is not None and repair.operation == "update",
                    ),
                    (
                        "addition_fixed",
                        repair is not None and "return a + b" in (repair.content or ""),
                    ),
                ]
        assertions = [{"name": name, "passed": passed} for name, passed in checks]
        return round(sum(passed for _, passed in checks) / len(checks), 4), assertions

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
