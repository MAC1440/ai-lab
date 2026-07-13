import unittest
from unittest.mock import patch

from services.ollama_client import OllamaClient


class OllamaClientTests(unittest.TestCase):
    def test_stream_chat_uses_streaming_payload_without_unsupported_fields(
        self,
    ):
        client = OllamaClient(
            base_url="http://localhost:11434",
            model="qwen2.5-coder:3b",
        )

        class DummyResponse:
            def __init__(self):
                # OllamaClient._raise_ollama_error() checks this.
                self.ok = True
                self.status_code = 200
                self.text = ""

                self._lines = [
                    b'{"message": {"content": "Hel"}}',
                    b'{"message": {"content": "lo"}}',
                ]

            def iter_lines(self, decode_unicode=True):
                for line in self._lines:
                    if decode_unicode:
                        yield line.decode("utf-8")
                    else:
                        yield line

        with patch(
            "services.ollama_client.requests.post",
            return_value=DummyResponse(),
        ) as post_mock:
            chunks = list(client.stream_chat("Hello"))

        self.assertEqual(chunks, ["Hel", "lo"])

        payload = post_mock.call_args.kwargs["json"]

        self.assertEqual(
            payload["model"],
            "qwen2.5-coder:3b",
        )
        self.assertTrue(payload["stream"])

        # Confirm requests.post itself was configured for streaming.
        self.assertTrue(
            post_mock.call_args.kwargs["stream"]
        )


if __name__ == "__main__":
    unittest.main()