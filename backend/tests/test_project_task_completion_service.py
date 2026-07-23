import unittest

from services.project_task_completion_service import (
    ProjectTaskCompletionService,
    VerificationProfileSelectionError,
)


class FakeTaskService:
    def __init__(self, task):
        self.task = task
        self.started = []
        self.finished = []

    def get_task(self, task_id):
        if task_id != self.task["task_id"]:
            raise LookupError(task_id)
        return self.task

    def record_verification_started(self, task_id, *, run_id, profile_id):
        self.started.append((task_id, run_id, profile_id))

    def record_verification_result(self, task_id, *, run, repair_task_id=None):
        self.finished.append((task_id, run["status"], repair_task_id))
        status = "completed" if run["status"] == "passed" else "needs_attention"
        return {**self.task, "status": status}


class FakeChangeService:
    def __init__(self):
        self.approved = []

    def approve_change_set(self, change_set_id):
        self.approved.append(change_set_id)
        return [{"proposal_id": "proposal-1", "status": "approved"}]


class FakeDetectionService:
    def __init__(self, profiles):
        self.profiles = profiles

    def inspect_workspace(self):
        return {"profiles": self.profiles}


class FakeVerificationService:
    def __init__(self, status="passed"):
        self.status = status
        self.calls = []

    async def run_events(self, *, profile_id, proposal_id=None):
        self.calls.append((profile_id, proposal_id))
        yield {"type": "verification_started", "run_id": "verify-1"}
        yield {
            "type": "verification_done",
            "result": {
                "run_id": "verify-1",
                "workspace": "/workspace",
                "status": self.status,
            },
        }


class FakeRepairService:
    def create_from_verification(self, run_id):
        return {"task_id": "repair-1", "source_run_id": run_id}


class ProjectTaskCompletionServiceTests(unittest.IsolatedAsyncioTestCase):
    def task(self, *, requested_profile=None):
        return {
            "task_id": "task-1",
            "workspace": "/workspace",
            "status": "awaiting_approval",
            "agent_id": "unity",
            "verification_profile_id": requested_profile,
            "current_change_set_id": "set-1",
            "proposals": [{"file_path": "Assets/Player.cs"}],
            "artifacts": [
                {
                    "artifact_type": "implementation_plan",
                    "payload": {"verification": ["unity compile"]},
                }
            ],
        }

    def service(self, task, *, profiles, verification_status="passed"):
        tasks = FakeTaskService(task)
        changes = FakeChangeService()
        verification = FakeVerificationService(verification_status)
        service = ProjectTaskCompletionService(
            task_service=tasks,
            change_service=changes,
            project_detection_service=FakeDetectionService(profiles),
            verification_service=verification,
            repair_service=FakeRepairService(),
        )
        return service, tasks, changes, verification

    async def test_approves_then_runs_best_matching_profile(self):
        task = self.task()
        profiles = [
            {
                "profile_id": "node-lint",
                "project_type": "node",
                "working_directory": ".",
                "name": "Lint",
                "description": "",
                "command": "npm run lint",
                "available": True,
            },
            {
                "profile_id": "unity-compile",
                "project_type": "unity",
                "working_directory": ".",
                "name": "Unity compile",
                "description": "",
                "command": "Unity -batchmode",
                "available": True,
            },
        ]
        service, tasks, changes, verification = self.service(
            task,
            profiles=profiles,
        )

        events = [
            event
            async for event in service.approve_and_verify_events(task_id="task-1")
        ]

        self.assertEqual(changes.approved, ["set-1"])
        self.assertEqual(verification.calls, [("unity-compile", None)])
        self.assertEqual(tasks.started, [("task-1", "verify-1", "unity-compile")])
        self.assertEqual(events[-1]["type"], "verification_done")
        self.assertEqual(events[-1]["task"]["status"], "completed")

    async def test_failed_check_links_repair_task(self):
        service, tasks, _, _ = self.service(
            self.task(requested_profile="unity-compile"),
            profiles=[
                {
                    "profile_id": "unity-compile",
                    "available": True,
                    "project_type": "unity",
                    "working_directory": ".",
                }
            ],
            verification_status="failed",
        )

        events = [
            event
            async for event in service.approve_and_verify_events(task_id="task-1")
        ]

        self.assertEqual(tasks.finished, [("task-1", "failed", "repair-1")])
        self.assertEqual(events[-1]["repair_task"]["task_id"], "repair-1")

    async def test_refuses_apply_without_available_profile(self):
        service, _, changes, _ = self.service(self.task(), profiles=[])

        with self.assertRaises(VerificationProfileSelectionError):
            async for _ in service.approve_and_verify_events(task_id="task-1"):
                pass

        self.assertEqual(changes.approved, [])


if __name__ == "__main__":
    unittest.main()
