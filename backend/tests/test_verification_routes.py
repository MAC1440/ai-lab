import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.verifications import router
from services.verification_service import VerificationUnavailableError


class FakeWorkspaceService:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def get_workspace(self) -> Path:
        return self.root


class FakeDetectionService:
    def __init__(self, root: Path):
        self.root = root

    def inspect_workspace(self):
        return {
            "workspace": str(self.root),
            "projects": [],
            "profiles": [],
        }


class FakeStore:
    def __init__(self, root: Path):
        self.root = root

    def list_runs(self, *, workspace, limit):
        return [
            {
                "run_id": "run-1",
                "workspace": workspace,
                "status": "passed",
            }
        ][:limit]

    def get_run(self, run_id):
        return {
            "run_id": run_id,
            "workspace": str(self.root),
            "status": "passed",
        }


class FakeVerificationService:
    async def run_events(self, *, profile_id, proposal_id=None):
        yield {
            "type": "verification_started",
            "run_id": "run-1",
            "profile_id": profile_id,
            "proposal_id": proposal_id,
        }
        yield {
            "type": "verification_done",
            "result": {
                "run_id": "run-1",
                "status": "passed",
            },
        }

    def cancel(self, run_id):
        return {
            "run_id": run_id,
            "cancellation_requested": True,
        }


class UnavailableVerificationService(FakeVerificationService):
    async def run_events(self, *, profile_id, proposal_id=None):
        del profile_id, proposal_id
        raise VerificationUnavailableError("Missing test dependency")
        yield  # pragma: no cover - keeps this an async generator


class VerificationRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def patched_dependencies(self, service=None):
        stack = ExitStack()
        stack.enter_context(
            patch(
                "routes.verifications.workspace_service",
                FakeWorkspaceService(self.root),
            )
        )
        stack.enter_context(
            patch(
                "routes.verifications.project_detection_service",
                FakeDetectionService(self.root),
            )
        )
        stack.enter_context(
            patch(
                "routes.verifications.verification_store",
                FakeStore(self.root),
            )
        )
        stack.enter_context(
            patch(
                "routes.verifications.verification_service",
                service or FakeVerificationService(),
            )
        )
        return stack

    def test_profiles_and_history_use_active_workspace(self):
        with self.patched_dependencies():
            profiles = self.client.get("/verifications/profiles")
            runs = self.client.get("/verifications/runs")

        self.assertEqual(profiles.status_code, 200)
        self.assertEqual(profiles.json()["workspace"], str(self.root))
        self.assertEqual(runs.status_code, 200)
        self.assertEqual(runs.json()["runs"][0]["workspace"], str(self.root))

    def test_stream_is_valid_ndjson_and_has_terminal_event(self):
        with self.patched_dependencies():
            response = self.client.post(
                "/verifications/run/stream",
                json={
                    "profile_id": "profile-1",
                    "proposal_id": "proposal-1",
                },
            )

        events = [
            json.loads(line) for line in response.text.splitlines() if line.strip()
        ]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(events[0]["type"], "verification_started")
        self.assertEqual(events[-1]["type"], "verification_done")

    def test_unavailable_profile_becomes_terminal_error_event(self):
        with self.patched_dependencies(UnavailableVerificationService()):
            response = self.client.post(
                "/verifications/run/stream",
                json={"profile_id": "profile-1"},
            )

        event = json.loads(response.text.strip())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(event["type"], "error")
        self.assertEqual(event["status_code"], 409)


if __name__ == "__main__":
    unittest.main()
