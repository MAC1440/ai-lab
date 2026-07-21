import sys
import tempfile
import unittest
from pathlib import Path

from services.project_detection_service import VerificationProfile
from services.verification_service import VerificationService
from services.verification_store import VerificationStore


class TemporaryWorkspaceService:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def get_workspace(self) -> Path:
        return self.root


class StaticDetectionService:
    def __init__(self, profile: VerificationProfile):
        self.profile = profile

    def get_profile(self, profile_id: str) -> VerificationProfile:
        if profile_id != self.profile.profile_id:
            raise LookupError(profile_id)
        return self.profile


class VerificationServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.workspace = TemporaryWorkspaceService(self.root)
        self.store = VerificationStore(self.root / "runs.sqlite3")

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    def build_service(
        self,
        code: str,
        *,
        timeout_seconds: int = 10,
        max_output_chars: int = 20_000,
    ) -> VerificationService:
        profile = VerificationProfile(
            profile_id="test-profile",
            name="Test profile",
            description="Test command",
            project_type="python",
            working_directory=".",
            command=(sys.executable, "-c", code),
            display_command="python -c <test>",
            timeout_seconds=timeout_seconds,
            available=True,
        )
        return VerificationService(
            workspace_service=self.workspace,
            project_detection_service=StaticDetectionService(profile),
            store=self.store,
            max_output_chars=max_output_chars,
        )

    async def collect(self, service: VerificationService):
        return [event async for event in service.run_events(profile_id="test-profile")]

    async def test_successful_command_streams_terminal_result(self):
        service = self.build_service("print('verification works')")

        events = await self.collect(service)

        self.assertEqual(events[0]["type"], "verification_started")
        self.assertIn("output", [event["type"] for event in events])
        self.assertEqual(events[-1]["type"], "verification_done")
        self.assertEqual(events[-1]["result"]["status"], "passed")
        self.assertEqual(events[-1]["result"]["exit_code"], 0)

    async def test_failed_command_is_a_completed_failed_run(self):
        service = self.build_service("import sys; print('broken'); sys.exit(7)")

        events = await self.collect(service)
        result = events[-1]["result"]

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["exit_code"], 7)
        self.assertIn("broken", result["output_excerpt"])

    async def test_output_is_truncated_in_persistent_history(self):
        service = self.build_service(
            "print('x' * 30000)",
            max_output_chars=10_000,
        )

        events = await self.collect(service)
        result = events[-1]["result"]

        self.assertTrue(result["output_truncated"])
        stored = self.store.get_run(result["run_id"])
        self.assertLessEqual(len(stored["output"]), 10_000)

    async def test_active_run_can_be_cancelled(self):
        service = self.build_service(
            "import time; print('started', flush=True); time.sleep(30)"
        )
        stream = service.run_events(profile_id="test-profile")

        started_event = await anext(stream)
        run_id = started_event["run_id"]
        await anext(stream)
        service.cancel(run_id)

        remaining = [event async for event in stream]

        self.assertEqual(remaining[-1]["type"], "verification_done")
        self.assertEqual(remaining[-1]["result"]["status"], "cancelled")

    async def test_closed_stream_does_not_leave_running_history(self):
        service = self.build_service("print('never reached')")
        stream = service.run_events(profile_id="test-profile")

        started_event = await anext(stream)
        await stream.aclose()

        stored = self.store.get_run(started_event["run_id"])
        self.assertEqual(stored["status"], "cancelled")

    def test_unity_compiler_error_fails_even_with_success_exit_code(self):
        profile = VerificationProfile(
            profile_id="unity-compile",
            name="Unity compile",
            description="Compile",
            project_type="unity",
            working_directory=".",
            command=("Unity",),
            display_command="Unity",
            timeout_seconds=10,
            available=True,
        )

        summary, error = VerificationService._validate_profile_result(
            profile=profile,
            output="Assets/Player.cs(4,2): error CS1002: ; expected",
        )

        self.assertEqual(summary, "")
        self.assertIn("compiler", error)

    def test_unity_nunit_results_are_authoritative(self):
        result_file = self.root / "results.xml"
        result_file.write_text(
            '<test-run result="Failed" total="3" passed="2" failed="1" />',
            encoding="utf-8",
        )
        profile = VerificationProfile(
            profile_id="unity-tests",
            name="Unity tests",
            description="Tests",
            project_type="unity",
            working_directory=".",
            command=("Unity",),
            display_command="Unity",
            timeout_seconds=10,
            available=True,
            result_file=str(result_file),
            result_format="nunit-xml",
        )

        summary, error = VerificationService._validate_profile_result(
            profile=profile,
            output="",
        )

        self.assertIn("total=3", summary)
        self.assertIn("failed=1", summary)
        self.assertIn("failures", error)


if __name__ == "__main__":
    unittest.main()
