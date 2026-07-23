from __future__ import annotations

import ast
import asyncio
import operator
import py_compile
import shutil
import tempfile
import time
from collections.abc import AsyncIterator, Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Literal
from uuid import uuid4

from services.change_service import ChangeService
from services.project_context_service import ProjectContextService
from services.project_detection_service import ProjectDetectionService
from services.project_task_orchestrator import ProjectTaskOrchestrator
from services.project_task_service import ProjectTaskService
from services.project_task_store import ProjectTaskStore
from services.reliability_benchmark_store import ReliabilityBenchmarkStore
from services.source_validation_service import SourceValidationService
from services.task_context_service import ImplementationPlan, TaskContextService
from services.task_model_client import TaskModelClient
from services.workspace_service import WorkspaceService

ReliabilitySuite = Literal["quick", "full"]
AgentOverride = Literal["assigned", "coding", "unity", "web"]
ScenarioValidator = Callable[[Path], list[tuple[str, bool, str]]]


class ReliabilityBenchmarkBusyError(RuntimeError):
    """Raised when another reliability benchmark is already running."""


@dataclass(frozen=True)
class ReliabilityScenario:
    scenario_id: str
    name: str
    description: str
    category: Literal["workflow", "safety"]
    project_type: Literal["python", "nextjs", "unity", "platform"]
    agent_id: Literal["coding", "unity", "web"] | None
    suites: frozenset[ReliabilitySuite]
    goal: str | None = None
    fixture_files: tuple[tuple[str, str], ...] = ()
    expected_operations: tuple[tuple[str, str], ...] = ()
    validator: ScenarioValidator | None = None

    def public(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "project_type": self.project_type,
            "agent_id": self.agent_id,
            "suites": sorted(self.suites),
            "model_calls": 2 if self.category == "workflow" else 0,
        }


class _FaultInjectingChangeService(ChangeService):
    """Apply one item and fail so the production rollback path is exercised."""

    def __init__(self, *args: Any, fail_after: int = 1, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fail_after = fail_after
        self.applied_for_test = 0

    def _apply_transaction_proposal(
        self,
        transaction_id: str,
        proposal: Any,
        target: Path,
    ) -> None:
        super()._apply_transaction_proposal(
            transaction_id,
            proposal,
            target,
        )
        self.applied_for_test += 1
        if self.applied_for_test >= self.fail_after:
            raise OSError("Injected benchmark write failure")


class ReliabilityBenchmarkService:
    """Exercise the real staged workflow inside disposable project fixtures."""

    def __init__(
        self,
        *,
        model_client: TaskModelClient,
        store: ReliabilityBenchmarkStore,
        work_root: Path,
    ) -> None:
        self.model_client = model_client
        self.store = store
        self.work_root = work_root.resolve()
        self.work_root.mkdir(parents=True, exist_ok=True)
        self._active_run_id: str | None = None
        self._active_lock = RLock()
        self._scenarios = self._build_scenarios()

    def list_scenarios(self) -> list[dict[str, Any]]:
        return [scenario.public() for scenario in self._scenarios]

    def list_runs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        return self.store.list_runs(limit=limit)

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self.store.get_run(run_id)

    async def run_events(
        self,
        *,
        suite: ReliabilitySuite,
        repetitions: int,
        agent_override: AgentOverride = "assigned",
    ) -> AsyncIterator[dict[str, Any]]:
        if suite not in {"quick", "full"}:
            raise ValueError("suite must be quick or full")
        if (
            not isinstance(repetitions, int)
            or isinstance(repetitions, bool)
            or repetitions < 1
            or repetitions > 3
        ):
            raise ValueError("repetitions must be between 1 and 3")
        if agent_override not in {"assigned", "coding", "unity", "web"}:
            raise ValueError("Unsupported agent override")

        selected = [
            scenario for scenario in self._scenarios if suite in scenario.suites
        ]
        expanded = [
            (scenario, repetition)
            for repetition in range(1, repetitions + 1)
            for scenario in selected
        ]
        run_id = uuid4().hex
        self._reserve(run_id)
        started_clock = time.monotonic()
        started_at = self._utc_now()
        run_directory = Path(
            tempfile.mkdtemp(
                prefix=f"{run_id}-",
                dir=self.work_root,
            )
        )
        self.store.create_run(
            {
                "run_id": run_id,
                "suite": suite,
                "agent_override": (
                    None if agent_override == "assigned" else agent_override
                ),
                "repetitions": repetitions,
                "started_at": started_at,
                "scenario_count": len(expanded),
            }
        )
        results: list[dict[str, Any]] = []

        try:
            yield {
                "type": "reliability_started",
                "run_id": run_id,
                "suite": suite,
                "repetitions": repetitions,
                "scenario_count": len(expanded),
                "workspace_policy": "isolated_disposable",
                "started_at": started_at,
            }
            for sequence, (scenario, repetition) in enumerate(
                expanded,
                start=1,
            ):
                effective_agent = (
                    scenario.agent_id
                    if agent_override == "assigned"
                    else agent_override
                )
                yield {
                    "type": "scenario_started",
                    "run_id": run_id,
                    "sequence": sequence,
                    "scenario": scenario.public(),
                    "repetition": repetition,
                    "agent_id": effective_agent,
                }
                scenario_started = time.monotonic()
                scenario_root = (
                    run_directory
                    / f"{sequence:02d}-{scenario.scenario_id}"
                )
                try:
                    if scenario.category == "workflow":
                        evidence = await self._run_workflow_scenario(
                            scenario,
                            root=scenario_root,
                            agent_id=str(effective_agent),
                        )
                    else:
                        evidence = self._run_safety_scenario(
                            scenario,
                            root=scenario_root,
                        )
                    assertions = evidence.pop("assertions")
                    score = self._score(assertions)
                    result = {
                        "scenario_id": scenario.scenario_id,
                        "repetition": repetition,
                        "category": scenario.category,
                        "project_type": scenario.project_type,
                        "agent_id": effective_agent,
                        "status": "passed" if score == 1.0 else "failed",
                        "duration_ms": self._duration_ms(scenario_started),
                        "score": score,
                        "assertions": assertions,
                        "metrics": evidence,
                        "error": None,
                        "created_at": self._utc_now(),
                    }
                except asyncio.CancelledError:
                    raise
                except Exception as error:  # noqa: BLE001
                    result = {
                        "scenario_id": scenario.scenario_id,
                        "repetition": repetition,
                        "category": scenario.category,
                        "project_type": scenario.project_type,
                        "agent_id": effective_agent,
                        "status": "error",
                        "duration_ms": self._duration_ms(scenario_started),
                        "score": 0.0,
                        "assertions": [],
                        "metrics": {},
                        "error": str(error)[:4000],
                        "created_at": self._utc_now(),
                    }
                self.store.add_result(
                    run_id,
                    sequence=sequence,
                    result=result,
                )
                results.append(result)
                yield {
                    "type": "scenario_done",
                    "run_id": run_id,
                    "sequence": sequence,
                    "result": result,
                }

            completed = self._finish(
                run_id,
                results=results,
                started_clock=started_clock,
            )
            yield {
                "type": "reliability_done",
                "run_id": run_id,
                "run": completed,
            }
        except asyncio.CancelledError:
            self._finish(
                run_id,
                results=results,
                started_clock=started_clock,
                forced_status="interrupted",
                error="The reliability benchmark stream was cancelled.",
            )
            raise
        except BaseException as error:
            self._finish(
                run_id,
                results=results,
                started_clock=started_clock,
                forced_status="error",
                error=str(error),
            )
            raise
        finally:
            shutil.rmtree(run_directory, ignore_errors=True)
            self._release(run_id)

    async def _run_workflow_scenario(
        self,
        scenario: ReliabilityScenario,
        *,
        root: Path,
        agent_id: str,
    ) -> dict[str, Any]:
        if not scenario.goal or not scenario.validator:
            raise RuntimeError(f"Workflow scenario is incomplete: {scenario.name}")
        self._materialize(root, scenario.fixture_files)
        state = root / ".benchmark-state"
        state.mkdir()

        workspace = WorkspaceService()
        workspace.set_workspace(str(root))
        changes = ChangeService(
            workspace,
            database_path=state / "changes.sqlite3",
        )
        detection = ProjectDetectionService(workspace)
        task_service = ProjectTaskService(
            workspace_service=workspace,
            change_service=changes,
            store=ProjectTaskStore(state / "project-tasks.sqlite3"),
        )
        orchestrator = ProjectTaskOrchestrator(
            task_service=task_service,
            project_context_service=ProjectContextService(
                workspace,
                detection,
            ),
            change_service=changes,
            model_client=self.model_client,
            source_validation_service=SourceValidationService(workspace),
        )
        task = task_service.create(
            title=scenario.name,
            goal=scenario.goal,
            agent_id=agent_id,
            max_attempts=1,
        )
        events = [
            event
            async for event in orchestrator.run_events(
                task_id=task["task_id"],
                run_id=uuid4().hex,
            )
        ]
        if not events or events[-1].get("type") != "done":
            raise RuntimeError("The staged workflow did not emit a done event")
        completed = events[-1]["task"]
        proposals = completed.get("proposals", [])
        actual_operations = sorted(
            (
                str(item["file_path"]).replace("\\", "/"),
                str(item["operation"]),
            )
            for item in proposals
        )
        expected_operations = sorted(scenario.expected_operations)
        assertions = [
            self._assertion(
                "task_reached_review",
                completed.get("status") == "awaiting_approval",
                f"status={completed.get('status')}",
            ),
            self._assertion(
                "exact_planned_operations",
                actual_operations == expected_operations,
                f"expected={expected_operations}; actual={actual_operations}",
            ),
        ]
        change_set_id = completed.get("current_change_set_id")
        if not change_set_id:
            raise RuntimeError("The completed task has no change set ID")
        approved = changes.approve_change_set(str(change_set_id))
        assertions.append(
            self._assertion(
                "transaction_applied_all_files",
                len(approved) == len(expected_operations)
                and {item["status"] for item in approved} == {"approved"},
                f"approved={len(approved)}",
            )
        )
        assertions.extend(
            self._assertion(name, passed, detail)
            for name, passed, detail in scenario.validator(root)
        )
        transactions = changes.list_transactions(
            change_set_id=str(change_set_id)
        )
        assertions.append(
            self._assertion(
                "transaction_committed",
                bool(transactions)
                and transactions[0].get("state") == "committed",
                (
                    f"state={transactions[0].get('state')}"
                    if transactions
                    else "transaction missing"
                ),
            )
        )
        model_runs = [
            artifact
            for artifact in completed.get("artifacts", [])
            if artifact.get("artifact_type")
            in {"planning_model_run", "generation_model_run"}
        ]
        usage = self._aggregate_usage(model_runs)
        models = sorted(
            {
                f"{item.get('payload', {}).get('provider_id')}/"
                f"{item.get('payload', {}).get('model')}"
                for item in model_runs
            }
        )
        return {
            "assertions": assertions,
            "task_id": task["task_id"],
            "change_set_id": change_set_id,
            "proposal_count": len(proposals),
            "model_calls": len(model_runs),
            "models": models,
            "usage": usage,
            "verification_kind": (
                "python_runtime"
                if scenario.project_type == "python"
                else "source_contract"
            ),
        }

    def _run_safety_scenario(
        self,
        scenario: ReliabilityScenario,
        *,
        root: Path,
    ) -> dict[str, Any]:
        root.mkdir(parents=True)
        handlers: dict[str, Callable[[Path], dict[str, Any]]] = {
            "stale_context_guard": self._stale_context_guard,
            "transaction_rollback": self._transaction_rollback,
            "restart_recovery": self._restart_recovery,
            "interrupted_run_recovery": self._interrupted_run_recovery,
        }
        try:
            handler = handlers[scenario.scenario_id]
        except KeyError as error:
            raise RuntimeError(
                f"No safety scenario handler: {scenario.scenario_id}"
            ) from error
        return handler(root)

    def _stale_context_guard(self, root: Path) -> dict[str, Any]:
        target = root / "src" / "state.py"
        target.parent.mkdir(parents=True)
        target.write_text("VALUE = 1\n", encoding="utf-8")
        workspace = WorkspaceService()
        workspace.set_workspace(str(root))
        context_service = TaskContextService(workspace)
        plan = ImplementationPlan.model_validate(
            {
                "summary": "Update state.",
                "files": [
                    {
                        "path": "src/state.py",
                        "operation": "update",
                        "reason": "Exercise stale file detection.",
                    }
                ],
                "verification": ["python"],
            }
        )
        context = context_service.compile(plan)
        target.write_text("VALUE = 2\n", encoding="utf-8")
        rejected = False
        message = ""
        try:
            context_service.assert_fresh(context)
        except ValueError as error:
            rejected = True
            message = str(error)
        return {
            "assertions": [
                self._assertion(
                    "stale_context_rejected",
                    rejected and "changed after planning" in message,
                    message or "no exception",
                )
            ],
            "fault": "source_mutated_after_context_freeze",
        }

    def _transaction_rollback(self, root: Path) -> dict[str, Any]:
        original_a = b"alpha = 1\r\n"
        original_b = b"beta = 1\n"
        (root / "a.py").write_bytes(original_a)
        (root / "b.py").write_bytes(original_b)
        workspace = WorkspaceService()
        workspace.set_workspace(str(root))
        changes = _FaultInjectingChangeService(
            workspace,
            database_path=root / "changes.sqlite3",
            fail_after=1,
        )
        change_set_id = uuid4().hex
        proposals = changes.propose_change_set(
            operations=[
                {
                    "path": "a.py",
                    "operation": "update",
                    "summary": "Update alpha.",
                    "content": "alpha = 2\n",
                },
                {
                    "path": "b.py",
                    "operation": "update",
                    "summary": "Update beta.",
                    "content": "beta = 2\n",
                },
            ],
            change_set_id=change_set_id,
        )
        failed = False
        try:
            changes.approve_change_set(change_set_id)
        except OSError:
            failed = True
        pending = changes.list_proposals(
            status="pending",
            change_set_id=change_set_id,
        )
        transactions = changes.list_transactions(
            change_set_id=change_set_id
        )
        return {
            "assertions": [
                self._assertion(
                    "fault_was_injected",
                    failed and changes.applied_for_test == 1,
                    f"applied_before_failure={changes.applied_for_test}",
                ),
                self._assertion(
                    "exact_bytes_restored",
                    (root / "a.py").read_bytes() == original_a
                    and (root / "b.py").read_bytes() == original_b,
                    "CRLF and LF snapshots compared byte-for-byte",
                ),
                self._assertion(
                    "proposals_returned_to_pending",
                    len(pending) == len(proposals),
                    f"pending={len(pending)}",
                ),
                self._assertion(
                    "transaction_marked_rolled_back",
                    bool(transactions)
                    and transactions[0].get("state") == "rolled_back",
                    (
                        f"state={transactions[0].get('state')}"
                        if transactions
                        else "transaction missing"
                    ),
                ),
            ],
            "fault": "io_failure_after_first_write",
        }

    def _restart_recovery(self, root: Path) -> dict[str, Any]:
        original = b"answer = 41\r\n"
        target = root / "answer.py"
        target.write_bytes(original)
        database_path = root / "changes.sqlite3"
        workspace = WorkspaceService()
        workspace.set_workspace(str(root))
        before_restart = ChangeService(
            workspace,
            database_path=database_path,
        )
        change_set_id = uuid4().hex
        proposal = before_restart.propose(
            file_path="answer.py",
            content="answer = 42\n",
            summary="Set the answer.",
            change_set_id=change_set_id,
        )
        transaction = before_restart.transaction_service.prepare(
            change_set_id=change_set_id,
            workspace=root,
            proposal_ids=[proposal["proposal_id"]],
            touched_paths=[target],
            staged_payloads={
                proposal["proposal_id"]: "answer = 42\n"
            },
        )
        transaction_id = transaction["transaction_id"]
        before_restart.transaction_service.mark_applying(transaction_id)
        target.write_text("answer = 42\n", encoding="utf-8")
        before_restart.transaction_service.record_applied(transaction_id, 1)

        after_restart = ChangeService(
            workspace,
            database_path=database_path,
        )
        recovered = after_restart.list_transactions(
            change_set_id=change_set_id
        )
        pending = after_restart.list_proposals(
            status="pending",
            change_set_id=change_set_id,
        )
        return {
            "assertions": [
                self._assertion(
                    "restart_restored_exact_bytes",
                    target.read_bytes() == original,
                    "Recovered snapshot compared byte-for-byte",
                ),
                self._assertion(
                    "restart_marked_recovered_rollback",
                    bool(recovered)
                    and recovered[0].get("state") == "recovered_rollback",
                    (
                        f"state={recovered[0].get('state')}"
                        if recovered
                        else "transaction missing"
                    ),
                ),
                self._assertion(
                    "restart_returned_proposal_to_review",
                    len(pending) == 1,
                    f"pending={len(pending)}",
                ),
            ],
            "fault": "process_stopped_mid_transaction",
        }

    @staticmethod
    def _interrupted_run_recovery(root: Path) -> dict[str, Any]:
        database_path = root / "reliability.sqlite3"
        first = ReliabilityBenchmarkStore(database_path)
        run_id = uuid4().hex
        first.create_run(
            {
                "run_id": run_id,
                "suite": "quick",
                "agent_override": None,
                "repetitions": 1,
                "started_at": ReliabilityBenchmarkService._utc_now(),
                "scenario_count": 1,
            }
        )
        restarted = ReliabilityBenchmarkStore(database_path)
        recovered = restarted.get_run(run_id)
        return {
            "assertions": [
                ReliabilityBenchmarkService._assertion(
                    "running_record_marked_interrupted",
                    recovered.get("status") == "interrupted",
                    f"status={recovered.get('status')}",
                ),
                ReliabilityBenchmarkService._assertion(
                    "interruption_reason_persisted",
                    "backend stopped" in str(recovered.get("error")).lower(),
                    str(recovered.get("error") or ""),
                ),
            ],
            "fault": "backend_restart_during_benchmark",
        }

    def _finish(
        self,
        run_id: str,
        *,
        results: list[dict[str, Any]],
        started_clock: float,
        forced_status: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        passed = sum(item["status"] == "passed" for item in results)
        failed = len(results) - passed
        rate = round(passed / len(results), 4) if results else 0.0
        status = forced_status or ("passed" if failed == 0 else "failed")
        return self.store.finish_run(
            run_id,
            status=status,
            finished_at=self._utc_now(),
            duration_ms=self._duration_ms(started_clock),
            passed_count=passed,
            failed_count=failed,
            pass_rate=rate,
            error=error,
        )

    def _reserve(self, run_id: str) -> None:
        with self._active_lock:
            if self._active_run_id is not None:
                raise ReliabilityBenchmarkBusyError(
                    "Another reliability benchmark is already running"
                )
            self._active_run_id = run_id

    def _release(self, run_id: str) -> None:
        with self._active_lock:
            if self._active_run_id == run_id:
                self._active_run_id = None

    @staticmethod
    def _materialize(
        root: Path,
        files: Iterable[tuple[str, str]],
    ) -> None:
        root.mkdir(parents=True, exist_ok=False)
        for relative, content in files:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="")

    @staticmethod
    def _aggregate_usage(model_runs: list[dict[str, Any]]) -> dict[str, int]:
        totals: dict[str, int] = {}
        for artifact in model_runs:
            usage = artifact.get("payload", {}).get("usage", {})
            if not isinstance(usage, dict):
                continue
            for key, value in usage.items():
                if isinstance(value, int) and not isinstance(value, bool):
                    totals[key] = totals.get(key, 0) + value
        return totals

    @staticmethod
    def _assertion(name: str, passed: bool, detail: str) -> dict[str, Any]:
        return {
            "name": name,
            "passed": bool(passed),
            "detail": detail[:1000],
        }

    @staticmethod
    def _score(assertions: list[dict[str, Any]]) -> float:
        if not assertions:
            return 0.0
        return round(
            sum(bool(item.get("passed")) for item in assertions)
            / len(assertions),
            4,
        )

    @staticmethod
    def _duration_ms(started_clock: float) -> int:
        return max(0, round((time.monotonic() - started_clock) * 1000))

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def _build_scenarios(cls) -> tuple[ReliabilityScenario, ...]:
        return (
            ReliabilityScenario(
                scenario_id="python_discount",
                name="Python discount behavior",
                description=(
                    "Update one existing Python function and execute it with "
                    "boundary-value assertions."
                ),
                category="workflow",
                project_type="python",
                agent_id="coding",
                suites=frozenset({"quick", "full"}),
                goal=(
                    "Update exactly src/pricing.py and no other file. Preserve "
                    "the function name and typed signature. Implement "
                    "discounted_price(total: float, percent: float) -> float so "
                    "it rejects percent values outside 0 through 100 with "
                    "ValueError and otherwise returns total reduced by that "
                    "percentage. Request Python verification."
                ),
                fixture_files=(
                    ("requirements.txt", ""),
                    (
                        "src/pricing.py",
                        (
                            "def discounted_price("
                            "total: float, percent: float) -> float:\n"
                            "    return total\n"
                        ),
                    ),
                ),
                expected_operations=(("src/pricing.py", "update"),),
                validator=cls._validate_python_discount,
            ),
            ReliabilityScenario(
                scenario_id="nextjs_status_card",
                name="Next.js status card",
                description=(
                    "Update an App Router page and create one typed presentational "
                    "component."
                ),
                category="workflow",
                project_type="nextjs",
                agent_id="web",
                suites=frozenset({"full"}),
                goal=(
                    "Use exactly two operations and no other files: update "
                    "src/app/page.tsx and create "
                    "src/components/status-card.tsx. The new StatusCard must "
                    "accept typed title and status props and render both. The "
                    "page must import StatusCard and render it with title "
                    "\"Workspace\" and status \"Ready\". Keep both as server "
                    "components; do not add use client. Request TypeScript "
                    "verification."
                ),
                fixture_files=(
                    (
                        "package.json",
                        (
                            '{"name":"reliability-next","private":true,'
                            '"scripts":{"typecheck":"tsc --noEmit"}}\n'
                        ),
                    ),
                    (
                        "tsconfig.json",
                        '{"compilerOptions":{"jsx":"preserve","strict":true}}\n',
                    ),
                    (
                        "src/app/page.tsx",
                        (
                            "export default function Page() {\n"
                            "  return <main>Loading</main>;\n"
                            "}\n"
                        ),
                    ),
                ),
                expected_operations=(
                    ("src/app/page.tsx", "update"),
                    ("src/components/status-card.tsx", "create"),
                ),
                validator=cls._validate_nextjs_status_card,
            ),
            ReliabilityScenario(
                scenario_id="unity_damage_info",
                name="Unity typed damage input",
                description=(
                    "Create a C# value type and update a MonoBehaviour to consume it."
                ),
                category="workflow",
                project_type="unity",
                agent_id="unity",
                suites=frozenset({"full"}),
                goal=(
                    "Use exactly two operations and no other files: create "
                    "Assets/Scripts/DamageInfo.cs and update "
                    "Assets/Scripts/PlayerHealth.cs. DamageInfo must be a public "
                    "readonly struct with public Amount and Source fields and a "
                    "constructor. PlayerHealth must remain a public MonoBehaviour "
                    "named PlayerHealth, keep serialized maxHealth, and expose "
                    "public void ApplyDamage(DamageInfo damage) that clamps health "
                    "to zero. Request Unity compile verification."
                ),
                fixture_files=(
                    (
                        "ProjectSettings/ProjectVersion.txt",
                        "m_EditorVersion: 6000.2.10f1\n",
                    ),
                    (
                        "Packages/manifest.json",
                        '{"dependencies":{}}\n',
                    ),
                    (
                        "Assets/Scripts/PlayerHealth.cs",
                        (
                            "using UnityEngine;\n\n"
                            "public class PlayerHealth : MonoBehaviour\n"
                            "{\n"
                            "    [SerializeField] private int maxHealth = 100;\n"
                            "    private int currentHealth;\n"
                            "}\n"
                        ),
                    ),
                ),
                expected_operations=(
                    ("Assets/Scripts/DamageInfo.cs", "create"),
                    ("Assets/Scripts/PlayerHealth.cs", "update"),
                ),
                validator=cls._validate_unity_damage,
            ),
            ReliabilityScenario(
                scenario_id="stale_context_guard",
                name="Stale context rejection",
                description=(
                    "Mutate a frozen source file and require generation to stop."
                ),
                category="safety",
                project_type="platform",
                agent_id=None,
                suites=frozenset({"quick", "full"}),
            ),
            ReliabilityScenario(
                scenario_id="transaction_rollback",
                name="Transactional rollback",
                description=(
                    "Fail after the first write and require exact-byte restoration."
                ),
                category="safety",
                project_type="platform",
                agent_id=None,
                suites=frozenset({"quick", "full"}),
            ),
            ReliabilityScenario(
                scenario_id="restart_recovery",
                name="Restart recovery",
                description=(
                    "Simulate process termination mid-apply and recover on restart."
                ),
                category="safety",
                project_type="platform",
                agent_id=None,
                suites=frozenset({"full"}),
            ),
            ReliabilityScenario(
                scenario_id="interrupted_run_recovery",
                name="Benchmark interruption recovery",
                description=(
                    "Ensure a running result becomes an interrupted durable record."
                ),
                category="safety",
                project_type="platform",
                agent_id=None,
                suites=frozenset({"full"}),
            ),
        )

    @staticmethod
    def _validate_python_discount(
        root: Path,
    ) -> list[tuple[str, bool, str]]:
        target = root / "src" / "pricing.py"
        syntax_ok = True
        syntax_detail = "compiled"
        try:
            py_compile.compile(str(target), doraise=True)
        except py_compile.PyCompileError as error:
            syntax_ok = False
            syntax_detail = str(error)

        behavior_ok = False
        behavior_detail = ""
        try:
            module = ast.parse(target.read_text(encoding="utf-8"))
            function = next(
                item
                for item in module.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name == "discounted_price"
            )
            return_node = next(
                item for item in function.body if isinstance(item, ast.Return)
            )
            if return_node.value is None:
                raise ValueError("discounted_price has no return value")
            normal = ReliabilityBenchmarkService._evaluate_numeric_expression(
                return_node.value,
                {"total": 200.0, "percent": 25.0},
            )
            zero = ReliabilityBenchmarkService._evaluate_numeric_expression(
                return_node.value,
                {"total": 80.0, "percent": 0.0},
            )
            conditions = [
                node
                for node in ast.walk(function)
                if isinstance(node, ast.If)
            ]
            raises_value_error = any(
                isinstance(node, ast.Raise)
                and isinstance(node.exc, ast.Call)
                and isinstance(node.exc.func, ast.Name)
                and node.exc.func.id == "ValueError"
                for node in ast.walk(function)
            )
            compared_values = {
                node.value
                for condition in conditions
                for node in ast.walk(condition.test)
                if isinstance(node, ast.Constant)
                and isinstance(node.value, (int, float))
            }
            percent_compared = any(
                isinstance(node, ast.Name) and node.id == "percent"
                for condition in conditions
                for node in ast.walk(condition.test)
            )
            rejected_low = (
                raises_value_error
                and percent_compared
                and 0 in compared_values
            )
            rejected_high = (
                raises_value_error
                and percent_compared
                and 100 in compared_values
            )
            behavior_ok = (
                normal == 150.0
                and zero == 80.0
                and rejected_low
                and rejected_high
            )
            behavior_detail = (
                f"normal={normal}; zero={zero}; "
                f"bounds={rejected_low}/{rejected_high}"
            )
        except (OSError, StopIteration, SyntaxError, TypeError, ValueError) as error:
            behavior_detail = str(error)
        return [
            ("python_syntax_valid", syntax_ok, syntax_detail),
            ("discount_behavior_correct", behavior_ok, behavior_detail),
        ]

    @staticmethod
    def _evaluate_numeric_expression(
        node: ast.expr,
        variables: dict[str, float],
    ) -> float:
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)
        ):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id in variables:
            return float(variables[node.id])
        if isinstance(node, ast.UnaryOp) and isinstance(
            node.op,
            (ast.UAdd, ast.USub),
        ):
            value = ReliabilityBenchmarkService._evaluate_numeric_expression(
                node.operand,
                variables,
            )
            return value if isinstance(node.op, ast.UAdd) else -value
        operations: dict[type[ast.operator], Callable[[float, float], float]] = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
        }
        if isinstance(node, ast.BinOp):
            operation = operations.get(type(node.op))
            if operation is not None:
                left = ReliabilityBenchmarkService._evaluate_numeric_expression(
                    node.left,
                    variables,
                )
                right = ReliabilityBenchmarkService._evaluate_numeric_expression(
                    node.right,
                    variables,
                )
                return operation(left, right)
        raise ValueError(
            "The benchmark return expression contains unsupported operations"
        )

    @staticmethod
    def _validate_nextjs_status_card(
        root: Path,
    ) -> list[tuple[str, bool, str]]:
        page = (root / "src/app/page.tsx").read_text(encoding="utf-8")
        component = (root / "src/components/status-card.tsx").read_text(
            encoding="utf-8"
        )
        return [
            (
                "page_imports_status_card",
                "StatusCard" in page and "status-card" in page,
                "Page import inspected",
            ),
            (
                "page_renders_required_values",
                "Workspace" in page and "Ready" in page,
                "Required prop values inspected",
            ),
            (
                "component_has_typed_props",
                "title" in component
                and "status" in component
                and (
                    "type " in component
                    or "interface " in component
                ),
                "Component prop contract inspected",
            ),
            (
                "server_component_boundary_preserved",
                "use client" not in page.lower()
                and "use client" not in component.lower(),
                "No client directive found",
            ),
        ]

    @staticmethod
    def _validate_unity_damage(
        root: Path,
    ) -> list[tuple[str, bool, str]]:
        damage = (root / "Assets/Scripts/DamageInfo.cs").read_text(
            encoding="utf-8"
        )
        health = (root / "Assets/Scripts/PlayerHealth.cs").read_text(
            encoding="utf-8"
        )
        compact_damage = " ".join(damage.split())
        compact_health = " ".join(health.split())
        return [
            (
                "damage_info_is_readonly_struct",
                "public readonly struct DamageInfo" in compact_damage,
                "DamageInfo declaration inspected",
            ),
            (
                "damage_info_has_required_data",
                "Amount" in damage
                and "Source" in damage
                and "DamageInfo(" in damage,
                "Fields and constructor inspected",
            ),
            (
                "player_health_type_preserved",
                "public class PlayerHealth : MonoBehaviour" in compact_health
                and "maxHealth" in health,
                "Unity component declaration inspected",
            ),
            (
                "apply_damage_is_bounded",
                "ApplyDamage(DamageInfo" in compact_health
                and (
                    "Mathf.Max" in health
                    or "Mathf.Clamp" in health
                    or "currentHealth < 0" in health
                ),
                "Damage method and lower bound inspected",
            ),
        ]
