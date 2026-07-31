import unittest
from unittest.mock import patch

from pydantic_ai import Agent
from pydantic_ai.models.function import DeltaToolCall, FunctionModel

from services.agent_runner import AgentRunner
from services.pydantic_agent import (
    AgentRunDeps,
    enforce_tool_policy,
    list_files,
    read_file,
    web_search,
)
from services.pydantic_runner import PydanticAgentRunner


class _AgentService:
    def __init__(self, *, use_rag: bool = False):
        self.use_rag = use_rag

    def get_agent(self, agent_id):
        return {
            "id": agent_id,
            "model": "test-model",
            "use_rag": self.use_rag,
            "system_prompt": "Test prompt",
        }

    def get_allowed_tool_names(self, agent_id):
        del agent_id
        return []


class _Client:
    model = "test-model"

    def __init__(self, *args, **kwargs):
        del args, kwargs

    def stream_chat_with_tools(self, **kwargs):
        del kwargs
        yield {
            "message": {
                "content": "done",
                "tool_calls": [],
            }
        }


class ContextAndToolRegressionTests(unittest.IsolatedAsyncioTestCase):
    def test_non_rag_legacy_agent_has_initialized_trace(self):
        runner = AgentRunner(agent_service=_AgentService())

        with patch(
            "services.agent_runner.OllamaClient",
            _Client,
        ):
            events = list(
                runner.run_events(
                    agent_id="web",
                    prompt="hello",
                )
            )

        result = events[-1]["result"]
        self.assertFalse(result["rag"]["enabled"])
        self.assertEqual(result["rag"]["included_count"], 0)
        self.assertEqual(result["answer"], "done")

    def test_structured_file_errors_are_returned(self):
        with patch(
            "services.pydantic_agent._list_files",
            side_effect=FileNotFoundError("missing"),
        ):
            result = list_files(None, ".")

        self.assertEqual(result["error_type"], "FileNotFoundError")
        self.assertIn("missing", result["error"])

    def test_web_search_normalizes_numeric_string(self):
        with patch(
            "services.pydantic_agent._web_search",
            return_value={"results": []},
        ) as search:
            result = web_search(None, "python docs", "5")

        self.assertEqual(result, {"results": []})
        search.assert_called_once_with(
            query="python docs",
            max_results=5,
        )

    async def test_read_file_accepts_range_arguments(self):
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
                            '{"file_path":"backend/app.py",'
                            '"start_line":1,"end_line":400}'
                        ),
                        tool_call_id="read-range-1",
                    )
                }
            else:
                yield "inspected"

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
                    "path": "backend/app.py",
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
                    prompt="Inspect backend/app.py",
                    tool_policy="inspect",
                )
            ]

        ranged_read.assert_called_once_with(
            file_path="backend/app.py",
            start_line=1,
            end_line=400,
        )
        self.assertEqual(events[-1]["type"], "done")
        self.assertEqual(request_count, 2)


if __name__ == "__main__":
    unittest.main()
