import os
from functools import lru_cache

from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider


@lru_cache(maxsize=10)
def get_ollama_model(model_name: str) -> OllamaModel:
    """Create and cache a Pydantic AI model connected to local Ollama."""

    base_url = os.getenv(
        "PYDANTIC_AI_OLLAMA_BASE_URL",
        "http://localhost:11434/v1",
    )

    provider = OllamaProvider(base_url=base_url)

    return OllamaModel(
        model_name,
        provider=provider,
    )