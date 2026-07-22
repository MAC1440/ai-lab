import unittest
from unittest.mock import patch

from pydantic_ai import Agent
from pydantic_ai.models.function import DeltaToolCall, FunctionModel

from services.pydantic_agent import (
    AgentRunDeps,
    enforce_tool_policy,
    propose_file_change,
    propose_file_change_set,
    read_file,
)
from services.pydantic_runner import PydanticAgentRunner


class PydanticAgentRunnerTests(unittest.IsolatedAsyncioTestCase):
    def test_rag_mode_overrides_general_profile(self):
        runner = PydanticAgentRunner()
        self.assertEqual(runner.max_model_requests, 16)
        self.assertEqual(
            runner._resolve_rag(
                profile_enabled=False,
                rag_mode="enabled",
                legacy_override=None,
            ),
            (True, "request"),
        )
        self.assertEqual(
            runner._resolve_rag(
                profile_enabled=True,
                rag_mode="disabled",
                legacy_override=None,
            ),
            (False, "request"),
        )

    def test_tool_override_can_only_reduce_profile_permissions(self):
        runner = PydanticAgentRunner()
        self.assertEqual(
            runner._resolve_tools(
                profile_tool_names=["read_file", "search_text"],
                tools_enabled=True,
                enabled_tools=["read_file"],
            ),
            {"read_file"},
        )
        with self.assertRaises(PermissionError):
            runner._resolve_tools(
                profile_tool_names=["read_file"],
                tools_enabled=True,
                enabled_tools=["propose_file_change"],
            )

    def test_tools_can_be_disabled_per_run(self):
        self.assertEqual(
            PydanticAgentRunner._resolve_tools(
                profile_tool_names=["read_file"],
                tools_enabled=False,
                enabled_tools=None,
            ),
            set(),
        )

    async def test_project_context_is_streamed_and_added_to_result(self):
        class DummyContextService:
            def build(self, *, prompt, agent_id):
                self.call = {"prompt": prompt, "agent_id": agent_id}
                return (
                    {
                        "enabled": True,
                        "workspace": "C:/workspace",
                        "project_types": ["python"],
                        "selected_project_root": "backend",
                        "files_included": ["backend/app.py"],
                        "file_count": 1,
                        "prompt_paths_found": ["backend/app.py"],
                        "tree_entries": 5,
                        "tree_truncated": False,
                        "characters": 100,
                        "max_characters": 7000,
                        "skipped_paths": [],
                    },
                    '<workspace_file path="backend/app.py">pass</workspace_file>',
                )

        captured_messages = []

        async def model_stream(messages, info):
            del info
            captured_messages.extend(messages)
            yield "Context received."

        agent = Agent(
            model=FunctionModel(stream_function=model_stream),
            deps_type=AgentRunDeps,
            tools=[read_file, propose_file_change],
        )
        context_service = DummyContextService()

        with patch(
            "services.pydantic_runner.get_pydantic_agent",
            return_value=agent,
        ):
            events = [
                event
                async for event in PydanticAgentRunner(
                    project_context_service=context_service,
                ).run_events(
                    agent_id="coding",
                    prompt="Inspect backend/app.py",
                )
            ]

        context_event = next(
            event for event in events if event["type"] == "context"
        )
        self.assertTrue(context_event["context"]["enabled"])
        self.assertEqual(
            events[-1]["result"]["context"]["files_included"],
            ["backend/app.py"],
        )
        self.assertEqual(context_service.call["agent_id"], "coding")
        self.assertIn("project_context", str(captured_messages))

    async def test_enforced_repair_stream_reads_then_proposes(self):
        request_count = 0

        async def model_stream(messages, info):
            nonlocal request_count
            del messages, info
            request_count += 1

            if request_count == 1:
                yield {
                    0: DeltaToolCall(
                        "read_file",
                        '{"file_path":"backend/app.py"}',
                        tool_call_id="read-1",
                    )
                }
            elif request_count == 2:
                yield {
                    0: DeltaToolCall(
                        "propose_file_change",
                        (
                            '{"file_path":"backend/app.py",'
                            '"old_text":"return 1",'
                            '"new_text":"return 2",'
                            '"summary":"Correct return value"}'
                        ),
                        tool_call_id="proposal-1",
                    )
                }
            else:
                yield "Proposal ready for review."

        agent = Agent(
            model=FunctionModel(stream_function=model_stream),
            deps_type=AgentRunDeps,
            tools=[read_file, propose_file_change],
            retries={"tools": 2, "output": 2},
        )
        agent.output_validator(enforce_tool_policy)

        with (
            patch(
                "services.pydantic_agent._read_file",
                return_value={
                    "path": "backend/app.py",
                    "content": "return 1",
                },
            ),
            patch(
                "services.pydantic_agent._propose_file_change",
                return_value={
                    "proposal": {"proposal_id": "proposal-1"}
                },
            ),
            patch(
                "services.pydantic_runner.get_pydantic_agent",
                return_value=agent,
            ),
        ):
            events = [
                event
                async for event in PydanticAgentRunner().run_events(
                    agent_id="coding",
                    prompt="Repair the failing test",
                    tool_policy="propose",
                )
            ]

        event_types = [event["type"] for event in events]
        self.assertNotIn("answer_delta", event_types)
        self.assertEqual(event_types[-1], "done")
        self.assertTrue(
            any(
                event["type"] == "status"
                and "choosing the next action" in event["message"]
                for event in events
            )
        )

        done_result = events[-1]["result"]
        self.assertEqual(done_result["answer"], "Proposal ready for review.")
        self.assertEqual(done_result["steps"], 3)
        self.assertEqual(
            [tool["name"] for tool in done_result["tools_used"]],
            ["read_file", "propose_file_change"],
        )
        self.assertTrue(
            all(
                tool["status"] == "success"
                for tool in done_result["tools_used"]
            )
        )

    async def test_malformed_change_set_is_rejected_then_recovers(self):
        request_count = 0

        async def model_stream(messages, info):
            nonlocal request_count
            del messages, info
            request_count += 1

            if request_count == 1:
                yield {
                    0: DeltaToolCall(
                        "propose_file_change_set",
                        (
                            '{"operations":[{"file_path":'
                            '"src/app/features/auth.tsx","operation":'
                            '"create","summary":"Add auth UI"}]}'
                        ),
                        tool_call_id="invalid-set",
                    )
                }
            elif request_count == 2:
                yield {
                    0: DeltaToolCall(
                        "read_file",
                        '{"file_path":"src/app/features/auth.tsx"}',
                        tool_call_id="read-auth",
                    ),
                    1: DeltaToolCall(
                        "read_file",
                        '{"file_path":"src/app/layout.tsx"}',
                        tool_call_id="read-layout",
                    ),
                }
            elif request_count == 3:
                yield {
                    0: DeltaToolCall(
                        "propose_file_change_set",
                        (
                            '{"operations":['
                            '{"file_path":"src/app/features/auth.tsx",'
                            '"new_text":"export function Auth() {}\\n",'
                            '"summary":"Add auth UI"},'
                            '{"file_path":"src/app/layout.tsx",'
                            '"new_text":"export default function Layout() {}\\n",'
                            '"summary":"Render auth UI"}'
                            ']}'
                        ),
                        tool_call_id="valid-set",
                    )
                }
            else:
                yield "Change set ready for review."

        agent = Agent(
            model=FunctionModel(stream_function=model_stream),
            deps_type=AgentRunDeps,
            tools=[read_file, propose_file_change_set],
            retries={"tools": 2, "output": 2},
        )
        agent.output_validator(enforce_tool_policy)

        def read_existing(path):
            return {"path": path, "content": "existing"}

        with (
            patch(
                "services.pydantic_agent._read_file",
                side_effect=read_existing,
            ),
            patch(
                "services.pydantic_agent._propose_file_change_set",
                return_value={
                    "change_set_id": "set-1",
                    "proposal_count": 2,
                    "proposals": [],
                },
            ) as propose_set,
            patch(
                "services.pydantic_runner.get_pydantic_agent",
                return_value=agent,
            ),
        ):
            events = [
                event
                async for event in PydanticAgentRunner(
                    max_model_requests=8,
                ).run_events(
                    agent_id="web",
                    prompt="Add login and signup pages",
                    tool_policy="propose",
                )
            ]

        self.assertEqual(request_count, 4)
        self.assertEqual(events[-1]["type"], "done")
        self.assertEqual(events[-1]["result"]["steps"], 4)
        self.assertEqual(propose_set.call_count, 1)
        operations = propose_set.call_args.kwargs["operations"]
        self.assertEqual(len(operations), 2)
        self.assertNotIn("operation", operations[0])
        self.assertIn("new_text", operations[0])

    async def test_repair_policy_rejects_agent_without_proposal_tool(self):
        runner = PydanticAgentRunner()

        with self.assertRaisesRegex(
            ValueError,
            "requires an agent with a workspace proposal tool",
        ):
            async for _ in runner.run_events(
                agent_id="general",
                prompt="Repair this",
                tool_policy="propose",
            ):
                pass


if __name__ == "__main__":
    unittest.main()
