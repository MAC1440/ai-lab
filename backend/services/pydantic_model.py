from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict

from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider


def build_pydantic_model(runtime: Dict[str, Any]):
    """Build a model from the current provider settings for one run."""

    provider = runtime["provider"]
    model_name = str(runtime.get("model") or "").strip()
    if not model_name:
        raise ValueError(
            "No model is configured for this run. Open the Models page, "
            "discover or pull a model, and save an agent assignment."
        )

    if provider["kind"] == "ollama":
        return OllamaModel(
            model_name,
            provider=OllamaProvider(
                base_url=f"{provider['base_url'].rstrip('/')}/v1",
                api_key=provider.get("api_key") or None,
            ),
        )

    return OpenAIChatModel(
        model_name,
        provider=OpenAIProvider(
            base_url=provider["base_url"],
            api_key=provider.get("api_key") or "not-required",
        ),
    )


@lru_cache(maxsize=10)
def get_ollama_model(model_name: str) -> OllamaModel:
    """Backward-compatible helper retained for existing tests and callers."""

    import os

    compatible_url = os.getenv(
        "PYDANTIC_AI_OLLAMA_BASE_URL", "http://localhost:11434/v1"
    )
    return OllamaModel(
        model_name,
        provider=OllamaProvider(base_url=compatible_url),
    )
