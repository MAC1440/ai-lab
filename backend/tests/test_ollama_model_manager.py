from __future__ import annotations

import json
import unittest

import httpx

from services.ollama_model_manager import OllamaModelManager


class OllamaModelManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_streams_download_progress_and_success(self):
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["authorization"] = request.headers.get(
                "Authorization"
            )
            captured["payload"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                content=(
                    b'{"status":"pulling manifest"}\n'
                    b'{"status":"downloading","digest":"sha256:a",'
                    b'"total":100,"completed":40}\n'
                    b'{"status":"success"}\n'
                ),
                headers={"Content-Type": "application/x-ndjson"},
            )

        transport = httpx.MockTransport(handler)

        def client_factory(**kwargs):
            return httpx.AsyncClient(
                transport=transport,
                **kwargs,
            )

        manager = OllamaModelManager(client_factory=client_factory)
        provider = {
            "id": "ollama",
            "kind": "ollama",
            "base_url": "http://localhost:11434",
            "api_key": "optional-secret",
        }

        events = [
            json.loads(line)
            async for line in manager.stream_pull(
                provider,
                "qwen3:4b",
            )
        ]

        self.assertEqual(
            captured["url"],
            "http://localhost:11434/api/pull",
        )
        self.assertEqual(
            captured["authorization"],
            "Bearer optional-secret",
        )
        self.assertEqual(
            captured["payload"],
            {
                "model": "qwen3:4b",
                "insecure": False,
                "stream": True,
            },
        )
        self.assertEqual(events[1]["percent"], 40.0)
        self.assertEqual(events[-1]["type"], "done")
        self.assertEqual(events[-1]["percent"], 100.0)

    async def test_stream_error_becomes_terminal_error_event(self):
        def handler(request: httpx.Request) -> httpx.Response:
            del request
            return httpx.Response(
                200,
                content=b'{"error":"authentication required"}\n',
                headers={"Content-Type": "application/x-ndjson"},
            )

        transport = httpx.MockTransport(handler)
        manager = OllamaModelManager(
            client_factory=lambda **kwargs: httpx.AsyncClient(
                transport=transport,
                **kwargs,
            )
        )
        provider = {
            "id": "ollama",
            "kind": "ollama",
            "base_url": "http://localhost:11434",
        }

        events = [
            json.loads(line)
            async for line in manager.stream_pull(
                provider,
                "qwen3.5:cloud",
            )
        ]

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "error")
        self.assertIn("authentication", events[0]["error"])

    def test_direct_cloud_provider_does_not_pull(self):
        provider = {
            "id": "ollama-cloud",
            "kind": "ollama",
            "base_url": "https://ollama.com",
        }

        with self.assertRaisesRegex(
            ValueError,
            "ready immediately",
        ):
            OllamaModelManager.validate_pull(
                provider,
                "gpt-oss:120b",
            )


if __name__ == "__main__":
    unittest.main()
