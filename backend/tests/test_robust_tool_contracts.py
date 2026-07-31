import inspect
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.models.function import DeltaToolCall, FunctionModel

from services.agent_runner import AgentRunner
from services.pydantic_agent import (
    AgentRunDeps,
    enforce_tool_policy,
    list_files,
    propose_file_change_set,
    read_file,
)
from services.pydantic_runner import PydanticAgentRunner


class _AgentService:
    def get_agent(self, agent_id):
        return {
            "id": agent_id,
            "model": "test-model",
            "use_rag": False,
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


class RobustToolContractTests(unittest.IsolatedAsyncioTestCase):
    def test_non_rag_legacy_agent_never_uses_unbound_context(self):
        runner = AgentRunner(agent_service=_AgentService())

        with patch("services.agent_runner.OllamaClient", _Client):
            events = list(
                runner.run_events(
                    agent_id="web",
                    prompt="hello",
                )
            )

        result = events[-1]["result"]
        self.assertEqual(result["answer"], "done")
        self.assertFalse(result["rag"]["enabled"])
        self.assertEqual(result["rag"]["included_count"], 0)

    def test_read_file_schema_is_strict_and_matches_registry(self):
        parameters = inspect.signature(read_file).parameters
        self.assertEqual(
            list(parameters),
            ["ctx", "file_path"],
        )

    def test_workspace_file_errors_propagate_for_framework_retry(self):
        with patch(
            "services.pydantic_agent._list_files",
            side_effect=FileNotFoundError("missing"),
        ):
            with self.assertRaisesRegex(
                FileNotFoundError,
                "missing",
            ):
                list_files(None, ".")

    def test_change_set_preflight_tracks_successful_wrapper_reads(self):
        deps = AgentRunDeps(tool_policy="propose")
        ctx = type("Context", (), {"deps": deps})()

        with (
            patch(
                "services.pydantic_agent._read_file",
                return_value={
                    "path": "backend/app.py",
                    "content": "old",
                },
            ),
            patch(
                "services.pydantic_agent._propose_file_change_set",
                return_value={"proposal_id": "p1"},
            ) as propose,
        ):
            result = propose_file_change_set(
                ctx,
                operations=[
                    {
                        "file_path": "backend/app.py",
                        "new_text": "new",
                    }
                ],
            )

        self.assertEqual(result, {"proposal_id": "p1"})
        self.assertIn("backend/app.py", deps.inspected_paths)
        propose.assert_called_once()

    async def test_invalid_read_file_range_shape_becomes_tool_retry(self):
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
                            '"start_line":1,"end_line":40}'
                        ),
                        tool_call_id="bad-read-1",
                    )
                }
            elif request_count == 2:
                yield {
                    0: DeltaToolCall(
                        "read_file_range",
                        (
                            '{"file_path":"backend/app.py",'
                            '"start_line":1,"end_line":40}'
                        ),
                        tool_call_id="good-read-1",
                    )
                }
            else:
                yield "inspected"

        from services.pydantic_agent import read_file_range

        agent = Agent(
            model=FunctionModel(stream_function=model_stream),
            deps_type=AgentRunDeps,
            tools=[read_file, read_file_range],
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
                    max_model_requests=6,
                ).run_events(
                    agent_id="coding",
                    prompt="Inspect backend/app.py",
                    tool_policy="inspect",
                )
            ]

        ranged_read.assert_called_once_with(
            file_path="backend/app.py",
            start_line=1,
            end_line=40,
        )
        self.assertEqual(events[-1]["type"], "done")
        self.assertEqual(request_count, 3)


if __name__ == "__main__":
    unittest.main()
