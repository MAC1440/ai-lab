import unittest
from unittest.mock import patch

from pydantic_ai import Agent
from pydantic_ai.models.function import DeltaToolCall, FunctionModel

from services.pydantic_agent import (
    AgentRunDeps,
    enforce_tool_policy,
    propose_file_change,
    read_file,
)
from services.pydantic_runner import PydanticAgentRunner


class PydanticAgentRunnerTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_repair_policy_rejects_agent_without_proposal_tool(self):
        runner = PydanticAgentRunner()

        with self.assertRaisesRegex(
            ValueError,
            "requires an agent with the propose_file_change tool",
        ):
            async for _ in runner.run_events(
                agent_id="general",
                prompt="Repair this",
                tool_policy="propose",
            ):
                pass


if __name__ == "__main__":
    unittest.main()
