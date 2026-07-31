import unittest
from unittest.mock import patch

from pydantic_ai import Agent
from pydantic_ai.models.function import FunctionModel

from services.pydantic_agent import AgentRunDeps
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


class PydanticRunnerStabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_non_rag_run_without_metrics_service_completes(self):
        async def model_stream(messages, info):
            del messages, info
            yield "Stable response."

        agent = Agent(
            model=FunctionModel(stream_function=model_stream),
            deps_type=AgentRunDeps,
        )
        runner = PydanticAgentRunner(agent_service=_AgentService())

        with patch(
            "services.pydantic_runner.get_pydantic_agent",
            return_value=agent,
        ):
            events = [
                event
                async for event in runner.run_events(
                    agent_id="general",
                    prompt="Hello",
                )
            ]

        final_metrics = next(
            event
            for event in events
            if event["type"] == "metrics"
            and event["metrics"]["final"]
        )
        self.assertEqual(
            final_metrics["metrics"]["metric_kind"],
            "measured",
        )
        self.assertIn("duration_seconds", final_metrics["metrics"])

        result = events[-1]["result"]
        self.assertEqual(result["answer"], "Stable response.")
        self.assertFalse(result["rag"]["enabled"])
        self.assertEqual(result["rag"]["included_count"], 0)
        self.assertIsInstance(result["runtime_metric"], dict)

    def test_history_keeps_tool_only_assistant_turn_and_result(self):
        history = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "read-1",
                        "function": {
                            "name": "read_file",
                            "arguments": {"file_path": "backend/app.py"},
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_name": "read_file",
                "tool_call_id": "read-1",
                "content": '{"path":"backend/app.py","content":"pass"}',
            },
        ]

        converted = PydanticAgentRunner._convert_history(history)
        rendered = str(converted)

        self.assertEqual(len(converted), 2)
        self.assertIn("read_file", rendered)
        self.assertIn("backend/app.py", rendered)
        self.assertIn("Tool result", rendered)


if __name__ == "__main__":
    unittest.main()
