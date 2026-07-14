import unittest

from services.pydantic_agent import get_pydantic_agent


class PydanticAgentTests(unittest.TestCase):
    def setUp(self):
        get_pydantic_agent.cache_clear()

    def tearDown(self):
        get_pydantic_agent.cache_clear()

    def test_creates_coding_agent(self):
        agent = get_pydantic_agent("coding")

        self.assertIsNotNone(agent)
        self.assertEqual(
            agent.model.model_name,
            "granite4.1:3b",
        )

    def test_caches_agent(self):
        first_agent = get_pydantic_agent("coding")
        second_agent = get_pydantic_agent("coding")

        self.assertIs(first_agent, second_agent)

    def test_rejects_unknown_agent(self):
        with self.assertRaises(ValueError):
            get_pydantic_agent("does-not-exist")


if __name__ == "__main__":
    unittest.main()