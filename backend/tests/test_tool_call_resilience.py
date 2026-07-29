import unittest
from unittest.mock import patch

from pydantic_ai import Agent
from pydantic_ai.models.function import DeltaToolCall, FunctionModel

from services.pydantic_agent import (
    AgentRunDeps,
    enforce_tool_policy,
    read_file,
)
from services.pydantic_runner import PydanticAgentRunner


class ToolCallResilienceTests(unittest.IsolatedAsyncioTestCase):
    def test_proposal_runs_have_completion_headroom(self):
        runner = PydanticAgentRunner(max_model_requests=16)

        self.assertEqual(runner._request_limit_for_policy("auto"), 16)
        self.assertEqual(runner._request_limit_for_policy("inspect"), 16)
        self.assertEqual(runner._request_limit_for_policy("propose"), 24)

    async def test_read_file_accepts_common_range_arguments(self):
        request_count = 0

        async def model_stream(messages, info):
            nonlocal request_count
            del messages, info
            request_count += 1

            if request_count == 1:
                yield {
                    0: DeltaToolCall(
                        "read_file",
                        (
                            '{"file_path":'
                            '"backend/tests/test_provider_settings_service.py",'
                            '"start_line":1,"end_line":400}'
                        ),
                        tool_call_id="read-range-1",
                    )
                }
            else:
                yield "The requested file range was inspected."

        agent = Agent(
            model=FunctionModel(stream_function=model_stream),
            deps_type=AgentRunDeps,
            tools=[read_file],
            retries={"tools": 2, "output": 2},
        )
        agent.output_validator(enforce_tool_policy)

        with (
            patch(
                "services.pydantic_agent._read_file_range",
                return_value={
                    "path": "backend/tests/test_provider_settings_service.py",
                    "start_line": 1,
                    "end_line": 180,
                    "total_lines": 180,
                    "content": "sample",
                },
            ) as ranged_read,
            patch(
                "services.pydantic_runner.get_pydantic_agent",
                return_value=agent,
            ),
        ):
            events = [
                event
                async for event in PydanticAgentRunner(
                    max_model_requests=4,
                ).run_events(
                    agent_id="coding",
                    prompt=(
                        "Inspect backend/tests/"
                        "test_provider_settings_service.py"
                    ),
                    tool_policy="inspect",
                )
            ]

        ranged_read.assert_called_once_with(
            file_path="backend/tests/test_provider_settings_service.py",
            start_line=1,
            end_line=400,
        )
        self.assertEqual(request_count, 2)
        self.assertEqual(events[-1]["type"], "done")
        self.assertEqual(
            events[-1]["result"]["answer"],
            "The requested file range was inspected.",
        )
        self.assertEqual(
            events[-1]["result"]["tools_used"][0]["status"],
            "success",
        )


if __name__ == "__main__":
    unittest.main()
