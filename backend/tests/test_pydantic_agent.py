import unittest
from types import SimpleNamespace

from pydantic_ai import ModelRetry

from services.pydantic_agent import (
    AgentRunDeps,
    enforce_tool_policy,
    get_pydantic_agent,
    propose_file_change,
    propose_file_change_set,
)


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

    def test_repair_policy_retries_text_only_answer(self):
        context = SimpleNamespace(
            deps=AgentRunDeps(tool_policy="propose")
        )

        with self.assertRaisesRegex(
            ModelRetry,
            "text-only solution is not accepted",
        ):
            enforce_tool_policy(context, "Here is how to fix it")

    def test_repair_policy_accepts_answer_after_proposal(self):
        deps = AgentRunDeps(tool_policy="propose")
        deps.inspected_paths.add("backend/app.py")
        deps.proposed_paths.add("backend/app.py")
        context = SimpleNamespace(deps=deps)

        output = enforce_tool_policy(context, "Proposal created")

        self.assertEqual(output, "Proposal created")

    def test_repair_policy_requires_reading_exact_target_first(self):
        context = SimpleNamespace(
            deps=AgentRunDeps(tool_policy="propose")
        )

        with self.assertRaisesRegex(ModelRetry, "exact target path"):
            propose_file_change(
                context,
                file_path="backend/app.py",
                old_text="return 1",
                new_text="return 2",
            )

    def test_change_set_requires_every_existing_target_to_be_read(self):
        context = SimpleNamespace(deps=AgentRunDeps(tool_policy="propose"))
        with self.assertRaisesRegex(ModelRetry, "Missing read"):
            propose_file_change_set(
                context,
                operations=[
                    {
                        "file_path": "backend/app.py",
                        "new_text": "updated",
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
