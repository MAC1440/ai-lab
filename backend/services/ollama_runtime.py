from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse


_CLOUD_MODEL_SUFFIXES = ("-cloud", ":cloud")


def routes_to_ollama_cloud(
    provider: Mapping[str, Any],
    model_name: str = "",
) -> bool:
    """Return whether an Ollama request is executed by Ollama Cloud.

    Direct cloud providers are detected from the hostname. Cloud models routed
    through a local Ollama daemon are detected from Ollama's cloud suffixes.
    """

    if provider.get("kind") != "ollama":
        return False

    hostname = (
        urlparse(str(provider.get("base_url") or "")).hostname or ""
    ).lower()
    normalized_model = model_name.strip().lower()

    return (
        hostname == "ollama.com"
        or hostname.endswith(".ollama.com")
        or normalized_model.endswith(_CLOUD_MODEL_SUFFIXES)
    )


def is_ollama_cloud_runtime(runtime: Mapping[str, Any]) -> bool:
    """Return whether a resolved AI Lab runtime routes through Ollama Cloud."""

    provider = runtime.get("provider")
    if not isinstance(provider, Mapping):
        return False

    return routes_to_ollama_cloud(
        provider,
        str(runtime.get("model") or ""),
    )


def ollama_model_settings_extra_body(
    runtime: Mapping[str, Any],
    context_window: int,
) -> dict[str, Any] | None:
    """Build local-only Ollama options for Pydantic AI model settings.

    Ollama's OpenAI-compatible API has no supported request field for changing
    context size. AI Lab preserves its existing local option for compatibility,
    but never sends that local runtime option to cloud-hosted models.
    """

    provider = runtime.get("provider")
    if not isinstance(provider, Mapping):
        return None
    if provider.get("kind") != "ollama":
        return None
    if is_ollama_cloud_runtime(runtime):
        return None

    return {"options": {"num_ctx": int(context_window)}}
