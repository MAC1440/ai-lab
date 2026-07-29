from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse


_CLOUD_MODEL_SUFFIXES = ("-cloud", ":cloud")


def is_direct_ollama_cloud_provider(
    provider: Mapping[str, Any],
) -> bool:
    """Return whether an Ollama provider points directly at ollama.com."""

    if provider.get("kind") != "ollama":
        return False

    hostname = (
        urlparse(str(provider.get("base_url") or "")).hostname or ""
    ).lower()
    return hostname == "ollama.com" or hostname.endswith(".ollama.com")


def routes_to_ollama_cloud(
    provider: Mapping[str, Any],
    model_name: str = "",
) -> bool:
    """Return whether an Ollama request is executed by Ollama Cloud."""

    normalized_model = model_name.strip().lower()
    return (
        is_direct_ollama_cloud_provider(provider)
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


def suggest_local_cloud_reference(model_name: str) -> str:
    """Suggest the model name used when cloud is routed by local Ollama.

    Ollama currently documents both ``:cloud`` and ``-cloud`` forms. Existing
    cloud names are preserved. A tagged direct-cloud name such as
    ``gpt-oss:120b`` becomes ``gpt-oss:120b-cloud``; an untagged name becomes
    ``<name>:cloud``. The frontend keeps the suggestion visible and editable.
    """

    clean = model_name.strip()
    lower = clean.lower()
    if lower.endswith(_CLOUD_MODEL_SUFFIXES):
        return clean

    if ":" in clean:
        repository, tag = clean.rsplit(":", 1)
        if repository and tag:
            return f"{repository}:{tag}-cloud"

    return f"{clean}:cloud"


def ollama_model_settings_extra_body(
    runtime: Mapping[str, Any],
    context_window: int,
) -> dict[str, Any] | None:
    """Build local-only Ollama options for Pydantic AI model settings."""

    provider = runtime.get("provider")
    if not isinstance(provider, Mapping):
        return None
    if provider.get("kind") != "ollama":
        return None
    if is_ollama_cloud_runtime(runtime):
        return None

    return {"options": {"num_ctx": int(context_window)}}
