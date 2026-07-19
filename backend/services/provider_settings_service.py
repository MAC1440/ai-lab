from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, Literal, Optional
from urllib.parse import urlparse

import httpx
import keyring
from pydantic import BaseModel, Field, field_validator


ProviderKind = Literal["ollama", "openai_compatible"]
KEYRING_SERVICE = "ai-lab-model-providers"


class ProviderInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: ProviderKind
    base_url: str = Field(min_length=1, max_length=500)
    api_key: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("name", "base_url")
    @classmethod
    def strip_required(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Value cannot be empty")
        return clean


class GenerationSettings(BaseModel):
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=128, le=32768)
    context_window: int = Field(default=8192, ge=1024, le=131072)


class AgentModelInput(BaseModel):
    provider_id: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=250)
    generation: GenerationSettings = Field(default_factory=GenerationSettings)

    @field_validator("provider_id", "model")
    @classmethod
    def strip_value(cls, value: str) -> str:
        return value.strip()


class ProviderSettingsService:
    """Persist provider metadata while keeping API keys out of the settings file."""

    def __init__(self, settings_path: str | Path) -> None:
        self.settings_path = Path(settings_path)
        self._lock = threading.RLock()
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_document()

    def snapshot(self, agent_ids: Iterable[str]) -> Dict[str, Any]:
        document = self._read()
        providers = [
            self._public_provider(provider)
            for provider in document["providers"].values()
        ]
        agents = {
            agent_id: self.resolve_agent(agent_id)
            for agent_id in agent_ids
        }
        return {"providers": providers, "agents": agents}

    def list_providers(self) -> list[Dict[str, Any]]:
        return [
            self._public_provider(provider)
            for provider in self._read()["providers"].values()
        ]

    def get_provider(self, provider_id: str, *, include_secret: bool = False) -> Dict[str, Any]:
        provider = self._read()["providers"].get(provider_id)
        if provider is None:
            raise ValueError(f"Unknown provider: {provider_id}")
        result = deepcopy(provider)
        if include_secret:
            result["api_key"] = self._get_secret(provider_id)
            return result
        return self._public_provider(result)

    def save_provider(self, provider_id: str, data: ProviderInput) -> Dict[str, Any]:
        self._validate_provider_id(provider_id)
        base_url = self._normalize_base_url(data.base_url, data.kind)
        with self._lock:
            document = self._read()
            existing = document["providers"].get(provider_id, {})
            document["providers"][provider_id] = {
                "id": provider_id,
                "name": data.name,
                "kind": data.kind,
                "base_url": base_url,
                "built_in": bool(existing.get("built_in", False)),
            }
            self._write(document)
            if data.api_key is not None:
                self._set_secret(provider_id, data.api_key.strip())
        return self._public_provider(document["providers"][provider_id])

    def delete_provider(self, provider_id: str) -> None:
        with self._lock:
            document = self._read()
            provider = document["providers"].get(provider_id)
            if provider is None:
                raise ValueError(f"Unknown provider: {provider_id}")
            if provider.get("built_in"):
                raise ValueError("The built-in Ollama provider cannot be deleted")
            in_use = [
                agent_id
                for agent_id, override in document["agents"].items()
                if override.get("provider_id") == provider_id
            ]
            if in_use:
                raise ValueError(
                    "Provider is assigned to: " + ", ".join(sorted(in_use))
                )
            del document["providers"][provider_id]
            self._write(document)
            self._delete_secret(provider_id)

    def save_agent(self, agent_id: str, data: AgentModelInput) -> Dict[str, Any]:
        with self._lock:
            document = self._read()
            if data.provider_id not in document["providers"]:
                raise ValueError(f"Unknown provider: {data.provider_id}")
            document["agents"][agent_id] = data.model_dump()
            self._write(document)
        return self.resolve_agent(agent_id)

    def resolve_agent(
        self,
        agent_id: str,
        *,
        fallback_model: str = "granite4.1:3b",
    ) -> Dict[str, Any]:
        document = self._read()
        override = document["agents"].get(agent_id)
        if override is None:
            override = {
                "provider_id": "ollama",
                "model": os.getenv("OLLAMA_MODEL", fallback_model),
                "generation": GenerationSettings().model_dump(),
            }
        provider = document["providers"].get(override["provider_id"])
        if provider is None:
            raise ValueError(
                f"Agent '{agent_id}' references missing provider "
                f"'{override['provider_id']}'"
            )
        return {
            **deepcopy(override),
            "provider": self._public_provider(provider),
        }

    def runtime_config(self, agent_id: str, fallback_model: str) -> Dict[str, Any]:
        resolved = self.resolve_agent(agent_id, fallback_model=fallback_model)
        provider = self.get_provider(
            resolved["provider_id"], include_secret=True
        )
        return {**resolved, "provider": provider}

    def discover_models(self, provider_id: str) -> Dict[str, Any]:
        provider = self.get_provider(provider_id, include_secret=True)
        headers = self._headers(provider)
        try:
            if provider["kind"] == "ollama":
                response = httpx.get(
                    f"{provider['base_url']}/api/tags", timeout=15.0
                )
                response.raise_for_status()
                raw_models = response.json().get("models", [])
                models = [
                    {
                        "name": item.get("name") or item.get("model"),
                        "size": item.get("size"),
                        "modified_at": item.get("modified_at"),
                        "warnings": self._model_warnings(
                            item.get("name") or item.get("model") or "",
                            item.get("size"),
                        ),
                    }
                    for item in raw_models
                    if item.get("name") or item.get("model")
                ]
            else:
                response = httpx.get(
                    f"{provider['base_url']}/models",
                    headers=headers,
                    timeout=15.0,
                )
                response.raise_for_status()
                models = [
                    {
                        "name": item.get("id"),
                        "size": None,
                        "modified_at": None,
                        "warnings": [],
                    }
                    for item in response.json().get("data", [])
                    if item.get("id")
                ]
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise RuntimeError(
                f"Could not list models from {provider['name']}: {error}"
            ) from error
        return {"provider": self._public_provider(provider), "models": models}

    def test_provider(self, provider_id: str) -> Dict[str, Any]:
        discovered = self.discover_models(provider_id)
        return {
            "ok": True,
            "message": (
                f"Connected successfully; found "
                f"{len(discovered['models'])} model(s)."
            ),
            **discovered,
        }

    @staticmethod
    def _model_warnings(model: str, size: Any) -> list[str]:
        warnings: list[str] = []
        size_bytes = size if isinstance(size, int) else 0
        lower = model.lower()
        if size_bytes > 8 * 1024**3:
            warnings.append(
                "This model is larger than 8 GB and may be slow with 16 GB RAM."
            )
        if any(token in lower for token in ("70b", "34b", "32b", "27b")):
            warnings.append("This model is not practical on the current 3 GB GPU.")
        elif any(token in lower for token in ("14b", "13b", "12b", "8b", "7b")):
            warnings.append(
                "Expect mostly CPU inference and slower tool loops on a 3 GB GPU."
            )
        return warnings

    @staticmethod
    def _headers(provider: Dict[str, Any]) -> Dict[str, str]:
        secret = provider.get("api_key")
        return {"Authorization": f"Bearer {secret}"} if secret else {}

    def _public_provider(self, provider: Dict[str, Any]) -> Dict[str, Any]:
        result = deepcopy(provider)
        result["api_key_configured"] = bool(self._get_secret(provider["id"]))
        result.pop("api_key", None)
        return result

    def _ensure_document(self) -> None:
        if self.settings_path.exists():
            return
        native_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._write(
            {
                "version": 1,
                "providers": {
                    "ollama": {
                        "id": "ollama",
                        "name": "Local Ollama",
                        "kind": "ollama",
                        "base_url": native_url.rstrip("/"),
                        "built_in": True,
                    }
                },
                "agents": {},
            }
        )

    def _read(self) -> Dict[str, Any]:
        with self._lock:
            try:
                data = json.loads(self.settings_path.read_text("utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise RuntimeError(f"Could not read provider settings: {error}") from error
            data.setdefault("providers", {})
            data.setdefault("agents", {})
            return data

    def _write(self, document: Dict[str, Any]) -> None:
        with self._lock:
            temporary = self.settings_path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.settings_path)

    @staticmethod
    def _validate_provider_id(provider_id: str) -> None:
        if not provider_id or any(
            char not in "abcdefghijklmnopqrstuvwxyz0123456789-_"
            for char in provider_id
        ):
            raise ValueError(
                "Provider id may only contain lowercase letters, numbers, - and _"
            )

    @staticmethod
    def _normalize_base_url(base_url: str, kind: ProviderKind) -> str:
        clean = base_url.strip().rstrip("/")
        parsed = urlparse(clean)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Provider URL must be an http:// or https:// URL")
        if kind == "ollama" and clean.endswith("/v1"):
            clean = clean[:-3].rstrip("/")
        if kind == "openai_compatible" and not clean.endswith("/v1"):
            clean = f"{clean}/v1"
        return clean

    @staticmethod
    def _get_secret(provider_id: str) -> Optional[str]:
        env_name = f"AI_LAB_PROVIDER_{provider_id.upper().replace('-', '_')}_API_KEY"
        try:
            return keyring.get_password(KEYRING_SERVICE, provider_id) or os.getenv(env_name)
        except keyring.errors.KeyringError:
            return os.getenv(env_name)

    @staticmethod
    def _set_secret(provider_id: str, secret: str) -> None:
        try:
            if secret:
                keyring.set_password(KEYRING_SERVICE, provider_id, secret)
            else:
                ProviderSettingsService._delete_secret(provider_id)
        except keyring.errors.KeyringError as error:
            raise RuntimeError(
                "The operating-system credential store rejected the API key. "
                "Configure it through AI_LAB_PROVIDER_<ID>_API_KEY instead."
            ) from error

    @staticmethod
    def _delete_secret(provider_id: str) -> None:
        try:
            keyring.delete_password(KEYRING_SERVICE, provider_id)
        except (keyring.errors.PasswordDeleteError, keyring.errors.KeyringError):
            pass
