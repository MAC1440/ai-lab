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
    is_ollama_cloud_runtime,
    ollama_model_settings_extra_body,
    routes_to_ollama_cloud,
)
from services.provider_settings_service import (
    ProviderInput,
    ProviderSettingsService,
)
from services.pydantic_model import build_pydantic_model
from services.task_model_client import _InferredCapabilityService


class OllamaCloudRuntimeTests(unittest.TestCase):
    def test_direct_ollama_cloud_provider_is_detected(self):
        runtime = {
            "model": "gpt-oss:120b",
            "provider": {
                "kind": "ollama",
                "base_url": "https://ollama.com",
            },
        }

        self.assertTrue(is_ollama_cloud_runtime(runtime))

    def test_cloud_suffixes_are_detected_through_local_ollama(self):
        provider = {
            "kind": "ollama",
            "base_url": "http://localhost:11434",
        }

        self.assertTrue(
            routes_to_ollama_cloud(provider, "gpt-oss:120b-cloud")
        )
        self.assertTrue(routes_to_ollama_cloud(provider, "glm-4.7:cloud"))
        self.assertFalse(routes_to_ollama_cloud(provider, "granite4.1:3b"))

    def test_local_num_ctx_options_are_not_sent_to_cloud(self):
        cloud_runtime = {
            "model": "gpt-oss:120b",
            "provider": {
                "kind": "ollama",
                "base_url": "https://ollama.com",
            },
        }
        local_runtime = {
            "model": "granite4.1:3b",
            "provider": {
                "kind": "ollama",
                "base_url": "http://localhost:11434",
            },
        }

        self.assertIsNone(
            ollama_model_settings_extra_body(cloud_runtime, 32768)
        )
        self.assertEqual(
            ollama_model_settings_extra_body(local_runtime, 8192),
            {"options": {"num_ctx": 8192}},
        )

    def test_inferred_task_capability_uses_tool_output_for_cloud(self):
        runtime = {
            "provider_id": "ollama-cloud",
            "model": "gpt-oss:120b",
            "generation": {
                "context_window": 32768,
                "max_tokens": 4096,
            },
            "provider": {
                "kind": "ollama",
                "base_url": "https://ollama.com",
            },
        }

        capability = _InferredCapabilityService.resolve_runtime(runtime)

        self.assertEqual(capability["structured_output_mode"], "tool")


class OllamaCloudProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.settings_path = (
            Path(self.temp_dir.name) / "provider-settings.json"
        )
        self.capabilities_path = (
            Path(self.temp_dir.name) / "model-capabilities.json"
        )
        self.secrets: dict[str, str] = {}

        get_secret = patch.object(
            ProviderSettingsService,
            "_get_secret",
            side_effect=lambda provider_id: self.secrets.get(provider_id),
        )
        set_secret = patch.object(
            ProviderSettingsService,
            "_set_secret",
            side_effect=lambda provider_id, value: self.secrets.__setitem__(
                provider_id,
                value,
            ),
        )
        delete_secret = patch.object(
            ProviderSettingsService,
            "_delete_secret",
            side_effect=lambda provider_id: self.secrets.pop(
                provider_id,
                None,
            ),
        )
        self.patchers = [get_secret, set_secret, delete_secret]
        for patcher in self.patchers:
            patcher.start()

        self.provider_service = ProviderSettingsService(self.settings_path)

    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.temp_dir.cleanup()

    def _save_cloud_provider(self):
        return self.provider_service.save_provider(
            "ollama-cloud",
            ProviderInput(
                name="Ollama Cloud",
                kind="ollama",
                base_url="https://ollama.com/api",
                api_key="cloud-secret",
            ),
        )

    def test_cloud_provider_url_is_normalized(self):
        provider = self._save_cloud_provider()

        self.assertEqual(provider["base_url"], "https://ollama.com")

    def test_cloud_model_discovery_sends_bearer_token(self):
        self._save_cloud_provider()
        response = httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "gpt-oss:120b",
                        "size": 70 * 1024**3,
                        "modified_at": "2026-07-01T00:00:00Z",
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
            result = self.provider_service.discover_models("ollama-cloud")

        get.assert_called_once_with(
            "https://ollama.com/api/tags",
            headers={"Authorization": "Bearer cloud-secret"},
            timeout=15.0,
        )
        self.assertEqual(result["models"][0]["name"], "gpt-oss:120b")
        self.assertIsNone(result["models"][0]["size"])
        self.assertTrue(
            any(
                "remote" in warning.lower()
                for warning in result["models"][0]["warnings"]
            )
        )

    def test_saved_native_profile_is_safely_downgraded_for_cloud(self):
        self._save_cloud_provider()
        capability_service = ModelCapabilityService(self.capabilities_path)
        capability_service.save_profile(
            ModelCapabilityInput(
                provider_id="ollama-cloud",
                model="gpt-oss:120b",
                context_window=32768,
                safe_input_tokens=26000,
                max_output_tokens=4096,
                structured_output_mode="native",
                supports_tools=True,
                supports_parallel_tools=False,
            )
        )
        runtime = {
            "provider_id": "ollama-cloud",
            "model": "gpt-oss:120b",
            "generation": {
                "context_window": 32768,
                "max_tokens": 4096,
            },
            "provider": self.provider_service.get_provider("ollama-cloud"),
        }

        capability = capability_service.resolve_runtime(runtime)

        self.assertEqual(capability["structured_output_mode"], "tool")
        self.assertEqual(
            capability["structured_output_fallback"],
            "ollama_cloud",
        )

    def test_model_builder_passes_ollama_api_key(self):
        runtime = {
            "model": "gpt-oss:120b",
            "provider": {
                "kind": "ollama",
                "base_url": "https://ollama.com",
                "api_key": "cloud-secret",
            },
        }
        provider_instance = object()

        with (
            patch(
                "services.pydantic_model.OllamaProvider",
                return_value=provider_instance,
            ) as provider_class,
            patch(
                "services.pydantic_model.OllamaModel"
            ) as model_class,
        ):
            build_pydantic_model(runtime)

        provider_class.assert_called_once_with(
            base_url="https://ollama.com/v1",
            api_key="cloud-secret",
        )
        model_class.assert_called_once_with(
            "gpt-oss:120b",
            provider=provider_instance,
        )


if __name__ == "__main__":
    unittest.main()
