import unittest
from unittest.mock import patch

from services.agent_runner import AgentRunner
from services.ollama_client import OllamaClient


class DummyRAGService:
    def search(self, query, top_k=3, distance_threshold=1.0):
        return {
            "chunks": ["NavMeshAgent requires a baked NavMesh."],
            "sources": [
                {
                    "source": "navmesh.md",
                    "chunk_index": 2,
                }
            ],
            "distances": [0.24],
            "distance_threshold": distance_threshold,
        }


class DummyToolExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, agent_id, tool_name, arguments):
        self.calls.append(
            {
                "agent_id": agent_id,
                "tool_name": tool_name,
                "arguments": arguments,
            }
        )
        return {
            "files": ["Assets/Scripts/PlayerMovement.cs"],
        }


class DummyStreamingOllamaClient:
    def __init__(self, model=None):
        self.model = model or "granite4.1:3b"
        self.calls = []

    def stream_chat_with_tools(self, messages, tools, options=None):
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
                "options": options,
            }
        )

        if len(self.calls) == 1:
            yield {
                "message": {
                    "content": "I will inspect the project.",
                },
                "done": False,
            }
            yield {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "list_files",
                                "arguments": {
                                    "folder": ".",
                                },
                            }
                        }
                    ],
                },
                "done": True,
            }
            return

        yield {
            "message": {
                "content": "The likely ",
            },
            "done": False,
        }
        yield {
            "message": {
                "content": "problem is the NavMesh setup.",
            },
            "done": True,
        }


class AgentRunnerStreamingTests(unittest.TestCase):
    def test_streams_rag_tool_and_final_answer_events(self):
        tool_executor = DummyToolExecutor()
        client = DummyStreamingOllamaClient()
        runner = AgentRunner(
            tool_executor=tool_executor,
            rag_service=DummyRAGService(),
        )

        with patch(
            "services.agent_runner.OllamaClient",
            return_value=client,
        ):
            events = list(
                runner.run_events(
                    agent_id="unity",
                    prompt="Why is my agent not moving?",
                )
            )

        event_types = [event["type"] for event in events]

        self.assertIn("rag", event_types)
        self.assertIn("tool_start", event_types)
        self.assertIn("tool_result", event_types)
        self.assertIn("answer_reset", event_types)
        self.assertEqual(event_types[-1], "done")

        rag_event = next(
            event for event in events if event["type"] == "rag"
        )
        self.assertTrue(rag_event["rag"]["context_found"])
        self.assertEqual(
            rag_event["rag"]["sources"][0]["source"],
            "navmesh.md",
        )

        tool_start = next(
            event for event in events if event["type"] == "tool_start"
        )
        tool_result = next(
            event for event in events if event["type"] == "tool_result"
        )
        self.assertEqual(tool_start["call_id"], tool_result["call_id"])
        self.assertEqual(tool_result["tool"]["status"], "success")

        done_event = events[-1]
        result = done_event["result"]
        self.assertEqual(
            result["answer"],
            "The likely problem is the NavMesh setup.",
        )
        self.assertEqual(result["steps"], 2)
        self.assertEqual(len(result["tools_used"]), 1)

        self.assertEqual(len(tool_executor.calls), 1)
        self.assertEqual(tool_executor.calls[0]["tool_name"], "list_files")

    def test_non_streaming_run_consumes_the_same_event_loop(self):
        client = DummyStreamingOllamaClient()
        runner = AgentRunner(
            tool_executor=DummyToolExecutor(),
            rag_service=DummyRAGService(),
        )

        with patch(
            "services.agent_runner.OllamaClient",
            return_value=client,
        ):
            result = runner.run(
                agent_id="unity",
                prompt="Why is my agent not moving?",
            )

        self.assertEqual(result["steps"], 2)
        self.assertTrue(result["rag"]["enabled"])
        self.assertEqual(len(result["tools_used"]), 1)


class OllamaToolStreamingTests(unittest.TestCase):
    def test_stream_chat_with_tools_uses_streaming_payload(self):
        client = OllamaClient(
            base_url="http://localhost:11434",
            model="granite4.1:3b",
        )

        class DummyResponse:
            def __init__(self):
                self.ok = True
                self.status_code = 200
                self.text = ""
                self._lines = [
                    b'{"message":{"content":"Hel"},"done":false}',
                    (
                        b'{"message":{"content":"lo",'
                        b'"tool_calls":[]},"done":true}'
                    ),
                ]

            def iter_lines(self, decode_unicode=True):
                for line in self._lines:
                    if decode_unicode:
                        yield line.decode("utf-8")
                    else:
                        yield line

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            }
        ]

        with patch(
            "services.ollama_client.requests.post",
            return_value=DummyResponse(),
        ) as post_mock:
            chunks = list(
                client.stream_chat_with_tools(
                    messages=[
                        {
                            "role": "user",
                            "content": "Hello",
                        }
                    ],
                    tools=tools,
                )
            )

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["message"]["content"], "Hel")

        payload = post_mock.call_args.kwargs["json"]
        self.assertTrue(payload["stream"])
        self.assertEqual(payload["tools"], tools)
        self.assertTrue(post_mock.call_args.kwargs["stream"])


if __name__ == "__main__":
    unittest.main()