import unittest

from pydantic import ValidationError

from routes.agents import AgentChatRequest


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


if __name__ == "__main__":
    unittest.main()
