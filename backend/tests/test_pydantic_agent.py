import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic_ai import ModelRetry

from services.pydantic_agent import (
    AgentRunDeps,
    FileChangeOperation,
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
        with (
            patch(
                "services.pydantic_agent._read_file",
                return_value={"path": "backend/app.py", "content": "old"},
            ),
            self.assertRaisesRegex(ModelRetry, "read_file\\('backend/app.py'\\)"),
        ):
            propose_file_change_set(
                context,
                operations=[
                    {
                        "file_path": "backend/app.py",
                        "new_text": "updated",
                    }
                ],
            )

    def test_change_set_operation_schema_rejects_vague_model_output(self):
        result = propose_file_change_set(
            SimpleNamespace(deps=AgentRunDeps(tool_policy="propose")),
            operations=[
                {
                    "file_path": "src/app/features/auth.tsx",
                    "operation": "create",
                    "summary": "Create authentication UI",
                }
            ],
        )

        self.assertEqual(result["error_type"], "ValidationError")
        self.assertIn("new_text", result["error"])
        self.assertIn("operation", result["error"])

    def test_change_set_schema_requires_content_and_forbids_operation_field(self):
        schema = FileChangeOperation.model_json_schema()

        self.assertEqual(schema["additionalProperties"], False)
        self.assertEqual(set(schema["required"]), {"file_path", "new_text"})
        self.assertNotIn("operation", schema["properties"])

    def test_new_change_set_target_does_not_require_fake_read(self):
        context = SimpleNamespace(deps=AgentRunDeps(tool_policy="propose"))
        with (
            patch(
                "services.pydantic_agent._read_file",
                side_effect=FileNotFoundError("not found"),
            ),
            patch(
                "services.pydantic_agent._propose_file_change_set",
                return_value={"change_set_id": "set-1", "proposals": []},
            ) as propose_set,
        ):
            result = propose_file_change_set(
                context,
                operations=[
                    {
                        "file_path": "src/app/login/page.tsx",
                        "new_text": "export default function Login() {}\n",
                        "summary": "Add login page",
                    }
                ],
            )

        self.assertEqual(result["change_set_id"], "set-1")
        self.assertIn("src/app/login/page.tsx", context.deps.proposed_paths)
        self.assertEqual(
            propose_set.call_args.kwargs["operations"][0],
            {
                "file_path": "src/app/login/page.tsx",
                "new_text": "export default function Login() {}\n",
                "old_text": "",
                "summary": "Add login page",
            },
        )


if __name__ == "__main__":
    unittest.main()
