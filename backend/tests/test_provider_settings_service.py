import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from services.provider_settings_service import (
    AgentModelInput,
    GenerationSettings,
    ProviderInput,
    ProviderSettingsService,
)


class ProviderSettingsServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "provider-settings.json"
        self.secrets = {}
        get_secret = patch.object(
            ProviderSettingsService,
            "_get_secret",
            side_effect=lambda provider_id: self.secrets.get(provider_id),
        )
        set_secret = patch.object(
            ProviderSettingsService,
            "_set_secret",
            side_effect=lambda provider_id, value: self.secrets.__setitem__(
                provider_id, value
            ),
        )
        delete_secret = patch.object(
            ProviderSettingsService,
            "_delete_secret",
            side_effect=lambda provider_id: self.secrets.pop(
                provider_id, None
            ),
        )
        self.patchers = [get_secret, set_secret, delete_secret]
        for patcher in self.patchers:
            patcher.start()
        self.service = ProviderSettingsService(self.path)

    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.temp_dir.cleanup()

    def test_defaults_to_local_ollama_without_configuration(self):
        runtime = self.service.runtime_config(
            "coding", "granite4.1:3b"
        )
        self.assertEqual(runtime["provider_id"], "ollama")
        self.assertEqual(runtime["model"], "granite4.1:3b")
        self.assertEqual(runtime["generation"]["temperature"], 0.1)

    def test_api_key_is_not_written_to_json(self):
        self.service.save_provider(
            "local-api",
            ProviderInput(
                name="Local API",
                kind="openai_compatible",
                base_url="http://localhost:1234",
                api_key="super-secret",
            ),
        )
        raw = self.path.read_text("utf-8")
        self.assertNotIn("super-secret", raw)
        self.assertTrue(
            self.service.get_provider("local-api")[
                "api_key_configured"
            ]
        )

    def test_agent_overrides_are_independent(self):
        self.service.save_agent(
            "coding",
            AgentModelInput(
                provider_id="ollama",
                model="qwen3:4b",
                generation=GenerationSettings(temperature=0.2),
            ),
        )
        coding = self.service.resolve_agent("coding")
        unity = self.service.resolve_agent("unity")
        self.assertEqual(coding["model"], "qwen3:4b")
        self.assertEqual(unity["model"], "granite4.1:3b")

    def test_openai_url_is_normalized_to_v1(self):
        provider = self.service.save_provider(
            "lm-studio",
            ProviderInput(
                name="LM Studio",
                kind="openai_compatible",
                base_url="http://localhost:1234/",
            ),
        )
        self.assertEqual(provider["base_url"], "http://localhost:1234/v1")

    def test_builtin_provider_cannot_be_deleted(self):
        with self.assertRaisesRegex(ValueError, "cannot be deleted"):
            self.service.delete_provider("ollama")

    def test_discovers_ollama_models_and_adds_hardware_warning(self):
        response = httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "large:14b",
                        "size": 9 * 1024**3,
                    }
                ]
            },
            request=httpx.Request("GET", "http://localhost/api/tags"),
        )
        with patch("services.provider_settings_service.httpx.get", return_value=response):
            result = self.service.discover_models("ollama")
        self.assertEqual(result["models"][0]["name"], "large:14b")
        self.assertGreaterEqual(len(result["models"][0]["warnings"]), 1)

    def test_settings_file_is_valid_json(self):
        document = json.loads(self.path.read_text("utf-8"))
        self.assertEqual(document["version"], 1)


if __name__ == "__main__":
    unittest.main()
