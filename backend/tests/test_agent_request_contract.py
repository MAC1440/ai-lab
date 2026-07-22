import unittest

from pydantic import ValidationError

from routes.agents import AgentChatRequest
from routes.project_tasks import CreateProjectTaskRequest


class AgentRequestContractTests(unittest.TestCase):
    def test_force_enabled_rag_contract_survives_validation(self):
        request = AgentChatRequest(
            prompt="Explain NavMeshAgent",
            rag_mode="enabled",
            rag_enabled=True,
        )
        self.assertEqual(request.rag_mode, "enabled")
        self.assertTrue(request.rag_enabled)

    def test_contradictory_rag_contract_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "conflicts"):
            AgentChatRequest(
                prompt="Explain NavMeshAgent",
                rag_mode="enabled",
                rag_enabled=False,
            )

    def test_unknown_request_fields_are_rejected(self):
        with self.assertRaises(ValidationError):
            AgentChatRequest(prompt="hello", rag_mod="enabled")

    def test_project_task_id_survives_request_validation(self):
        request = AgentChatRequest(
            prompt="Implement the task",
            project_task_id="task-12345",
        )
        self.assertEqual(request.project_task_id, "task-12345")

    def test_project_task_api_defaults_to_coding_not_unity(self):
        request = CreateProjectTaskRequest(
            title="Authentication page",
            goal="Add login and signup pages.",
        )

        self.assertEqual(request.agent_id, "coding")


if __name__ == "__main__":
    unittest.main()
