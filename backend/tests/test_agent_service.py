import unittest

from services.agent_service import AgentService


class AgentServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = AgentService()

    def test_exposes_web_and_unity_coding_agents(self):
        agents = {agent["id"]: agent for agent in self.service.list_agents()}
        self.assertIn("web", agents)
        self.assertIn("unity", agents)
        self.assertFalse(agents["web"]["use_rag"])
        self.assertTrue(agents["unity"]["use_rag"])

    def test_coding_profiles_only_receive_proposal_mutations(self):
        for agent_id in ("web", "unity", "coding"):
            tools = self.service.get_allowed_tool_names(agent_id)
            self.assertIn("propose_file_change", tools)
            self.assertIn("propose_path_operation", tools)
            self.assertNotIn("write_file", tools)

    def test_recommendations_prioritize_unity_then_web(self):
        self.assertEqual(
            self.service.recommend_agent(["node", "unity"])["agent_id"],
            "unity",
        )
        self.assertEqual(
            self.service.recommend_agent(["python"])["agent_id"],
            "web",
        )
        self.assertEqual(
            self.service.recommend_agent([])["agent_id"],
            "coding",
        )

    def test_returned_config_is_a_copy(self):
        first = self.service.get_agent("web")
        first["tools"].clear()
        self.assertTrue(self.service.get_agent("web")["tools"])


if __name__ == "__main__":
    unittest.main()
