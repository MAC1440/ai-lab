import tempfile
import unittest
from pathlib import Path

from services.model_capability_service import (
    ModelCapabilityInput,
    ModelCapabilityService,
)


class ModelCapabilityServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "capabilities.json"
        self.service = ModelCapabilityService(self.path)

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def runtime():
        return {
            "provider_id": "ollama",
            "model": "coder:7b",
            "provider": {"kind": "ollama"},
            "generation": {"context_window": 32768, "max_tokens": 8192},
        }

    def test_unprofiled_ollama_model_uses_visible_inferred_profile(self):
        resolved = self.service.resolve_runtime(self.runtime())
        self.assertEqual(resolved["profile_source"], "inferred")
        self.assertEqual(resolved["structured_output_mode"], "native")
        self.assertGreater(resolved["effective_safe_input_tokens"], 0)

    def test_saved_profile_clamps_unsafe_generation_settings(self):
        self.service.save_profile(
            ModelCapabilityInput(
                provider_id="ollama",
                model="coder:7b",
                context_window=16384,
                safe_input_tokens=10000,
                max_output_tokens=4096,
                structured_output_mode="native",
                estimated_characters_per_token=2.5,
            )
        )
        resolved = self.service.resolve_runtime(self.runtime())
        self.assertEqual(resolved["profile_source"], "saved")
        self.assertEqual(resolved["effective_context_window"], 16384)
        self.assertEqual(resolved["effective_max_output_tokens"], 4096)
        self.assertEqual(resolved["effective_safe_input_tokens"], 10000)

    def test_profile_rejects_input_budget_that_consumes_output_reserve(self):
        with self.assertRaisesRegex(ValueError, "leave room"):
            self.service.save_profile(
                ModelCapabilityInput(
                    provider_id="ollama",
                    model="coder:7b",
                    context_window=8192,
                    safe_input_tokens=7000,
                    max_output_tokens=2048,
                )
            )

    def test_unsupported_structured_output_blocks_task_stage(self):
        self.service.save_profile(
            ModelCapabilityInput(
                provider_id="ollama",
                model="coder:7b",
                context_window=8192,
                structured_output_mode="unsupported",
            )
        )
        with self.assertRaisesRegex(ValueError, "structured output"):
            self.service.require_structured_stage(self.runtime(), "planning")

    def test_profiles_survive_restart(self):
        saved = self.service.save_profile(
            ModelCapabilityInput(
                provider_id="ollama",
                model="coder:7b",
                context_window=16384,
            )
        )
        restored = ModelCapabilityService(self.path).get_profile(
            "ollama", "coder:7b"
        )
        self.assertEqual(restored["updated_at"], saved["updated_at"])


if __name__ == "__main__":
    unittest.main()
