from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from services.model_capability_service import (
    ModelCapabilityInput,
    ModelCapabilityService,
)
from services.ollama_runtime import (
    suggest_local_cloud_reference,
)
from services.provider_settings_service import (
    ProviderInput,
    ProviderSettingsService,
)


class ModelProviderManagementTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.secrets: dict[str, str] = {}

        self.patchers = [
            patch.object(
                ProviderSettingsService,
                "_get_secret",
                side_effect=lambda provider_id: self.secrets.get(
                    provider_id
                ),
            ),
            patch.object(
                ProviderSettingsService,
                "_set_secret",
                side_effect=lambda provider_id, secret: self.secrets.__setitem__(
                    provider_id,
                    secret,
                ),
            ),
            patch.object(
                ProviderSettingsService,
                "_delete_secret",
                side_effect=lambda provider_id: self.secrets.pop(
                    provider_id,
                    None,
                ),
            ),
        ]
        for patcher in self.patchers:
            patcher.start()

        self.service = ProviderSettingsService(
            self.root / "provider-settings.json"
        )

    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.temporary.cleanup()

    def test_agent_is_unconfigured_without_saved_or_environment_model(self):
        with patch.dict("os.environ", {}, clear=True):
            resolved = self.service.resolve_agent("coding")
            self.assertEqual(resolved["model"], "")
            self.assertEqual(
                resolved["assignment_source"],
                "unconfigured",
            )
            with self.assertRaisesRegex(
                ValueError,
                "No model is configured",
            ):
                self.service.runtime_config("coding", "")

    def test_explicit_agent_profile_fallback_remains_supported(self):
        runtime = self.service.runtime_config(
            "coding",
            "qwen3:4b",
        )

        self.assertEqual(runtime["model"], "qwen3:4b")
        self.assertEqual(
            runtime["assignment_source"],
            "agent_profile",
        )

    def test_cloud_provider_lists_ready_models_with_authentication(self):
        provider = self.service.save_provider(
            "ollama-cloud",
            ProviderInput(
                name="Ollama Cloud",
                kind="ollama",
                base_url="https://ollama.com/api",
                api_key="cloud-key",
            ),
        )
        self.assertTrue(provider["is_cloud"])
        self.assertFalse(provider["supports_pull"])
        self.assertEqual(provider["base_url"], "https://ollama.com")

        response = httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "gpt-oss:120b",
                        "digest": "sha256:test",
                        "details": {
                            "family": "gpt-oss",
                            "parameter_size": "120B",
                        },
                    }
                ]
            },
            request=httpx.Request(
                "GET",
                "https://ollama.com/api/tags",
            ),
        )

        with patch(
            "services.provider_settings_service.httpx.get",
            return_value=response,
        ) as get:
            result = self.service.discover_models("ollama-cloud")

        get.assert_called_once_with(
            "https://ollama.com/api/tags",
            headers={"Authorization": "Bearer cloud-key"},
            timeout=15.0,
        )
        model = result["models"][0]
        self.assertEqual(model["availability"], "cloud")
        self.assertTrue(model["ready"])
        self.assertEqual(
            model["pull_name"],
            "gpt-oss:120b-cloud",
        )
        self.assertIsNone(model["size"])

    def test_saved_native_capability_is_downgraded_for_cloud(self):
        self.service.save_provider(
            "ollama-cloud",
            ProviderInput(
                name="Ollama Cloud",
                kind="ollama",
                base_url="https://ollama.com",
                api_key="cloud-key",
            ),
        )
        capabilities = ModelCapabilityService(
            self.root / "model-capabilities.json"
        )
        capabilities.save_profile(
            ModelCapabilityInput(
                provider_id="ollama-cloud",
                model="gpt-oss:120b",
                context_window=32768,
                safe_input_tokens=26000,
                max_output_tokens=4096,
                structured_output_mode="native",
            )
        )
        runtime = {
            "provider_id": "ollama-cloud",
            "model": "gpt-oss:120b",
            "generation": {
                "context_window": 32768,
                "max_tokens": 4096,
            },
            "provider": self.service.get_provider("ollama-cloud"),
        }

        profile = capabilities.resolve_runtime(runtime)

        self.assertEqual(profile["structured_output_mode"], "tool")
        self.assertEqual(
            profile["structured_output_fallback"],
            "ollama_cloud",
        )

    def test_cloud_reference_suggestion_preserves_existing_forms(self):
        self.assertEqual(
            suggest_local_cloud_reference("qwen3.5:cloud"),
            "qwen3.5:cloud",
        )
        self.assertEqual(
            suggest_local_cloud_reference("gpt-oss:120b"),
            "gpt-oss:120b-cloud",
        )
        self.assertEqual(
            suggest_local_cloud_reference("kimi-k2.5"),
            "kimi-k2.5:cloud",
        )


if __name__ == "__main__":
    unittest.main()
