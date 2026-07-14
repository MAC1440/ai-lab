import os
import unittest
from unittest.mock import patch

from services.pydantic_model import get_ollama_model


class PydanticModelTests(unittest.TestCase):
    def setUp(self):
        get_ollama_model.cache_clear()

    def tearDown(self):
        get_ollama_model.cache_clear()

    def test_creates_and_caches_ollama_model(self):
        with patch.dict(
            os.environ,
            {
                "PYDANTIC_AI_OLLAMA_BASE_URL":
                    "http://localhost:11434/v1"
            },
        ):
            first_model = get_ollama_model("granite4.1:3b")
            second_model = get_ollama_model("granite4.1:3b")

        self.assertIs(first_model, second_model)
        self.assertEqual(first_model.model_name, "granite4.1:3b")


if __name__ == "__main__":
    unittest.main()