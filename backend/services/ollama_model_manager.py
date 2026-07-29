from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable, Mapping
from typing import Any

import httpx

from services.ollama_runtime import is_direct_ollama_cloud_provider


ClientFactory = Callable[..., httpx.AsyncClient]


class OllamaModelManager:
    """Stream model pulls through a configured local Ollama provider."""

    def __init__(
        self,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._client_factory = client_factory or httpx.AsyncClient

    @staticmethod
    def validate_pull(
        provider: Mapping[str, Any],
        model_name: str,
    ) -> str:
        clean_model = model_name.strip()

        if provider.get("kind") != "ollama":
            raise ValueError(
                "Only Ollama providers support model pulls."
            )
        if is_direct_ollama_cloud_provider(provider):
            raise ValueError(
                "Direct Ollama Cloud models are ready immediately and do not "
                "need to be pulled. Select the model directly, or pull its "
                "cloud reference through a local Ollama provider."
            )
        if not clean_model:
            raise ValueError("Model name cannot be empty.")
        if len(clean_model) > 250:
            raise ValueError("Model name is too long.")
        if any(ord(character) < 32 for character in clean_model):
            raise ValueError(
                "Model name cannot contain control characters."
            )

        return clean_model

    async def stream_pull(
        self,
        provider: Mapping[str, Any],
        model_name: str,
        *,
        insecure: bool = False,
    ) -> AsyncIterator[str]:
        """Yield normalized NDJSON pull events.

        Ollama streams newline-delimited JSON. AI Lab preserves status, digest,
        completed bytes, total bytes, and a calculated percentage when those
        fields are available.
        """

        model = self.validate_pull(provider, model_name)
        provider_id = str(provider.get("id") or "ollama")
        base_url = str(provider.get("base_url") or "").rstrip("/")
        headers = self._headers(provider)
        timeout = httpx.Timeout(
            connect=15.0,
            read=None,
            write=60.0,
            pool=15.0,
        )
        saw_success = False

        try:
            async with self._client_factory(
                timeout=timeout,
                follow_redirects=True,
            ) as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/api/pull",
                    headers=headers,
                    json={
                        "model": model,
                        "insecure": insecure,
                        "stream": True,
                    },
                ) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        detail = self._error_detail(body)
                        yield self._encode(
                            self._error_event(
                                provider_id,
                                model,
                                (
                                    f"Ollama pull failed with status "
                                    f"{response.status_code}: {detail}"
                                ),
                            )
                        )
                        return

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue

                        try:
                            payload = json.loads(line)
                        except json.JSONDecodeError:
                            yield self._encode(
                                self._error_event(
                                    provider_id,
                                    model,
                                    "Ollama returned malformed pull progress.",
                                )
                            )
                            return

                        if not isinstance(payload, dict):
                            continue

                        error = payload.get("error")
                        if isinstance(error, str) and error:
                            yield self._encode(
                                self._error_event(
                                    provider_id,
                                    model,
                                    error,
                                )
                            )
                            return

                        event = self._progress_event(
                            provider_id,
                            model,
                            payload,
                        )
                        if event["type"] == "done":
                            saw_success = True
                        yield self._encode(event)

        except httpx.TimeoutException:
            yield self._encode(
                self._error_event(
                    provider_id,
                    model,
                    "The model pull timed out while connecting to Ollama.",
                )
            )
            return
        except httpx.RequestError as error:
            yield self._encode(
                self._error_event(
                    provider_id,
                    model,
                    f"Could not reach Ollama: {error}",
                )
            )
            return

        if not saw_success:
            yield self._encode(
                self._error_event(
                    provider_id,
                    model,
                    "Ollama ended the pull stream without a success event.",
                )
            )

    @staticmethod
    def _headers(provider: Mapping[str, Any]) -> dict[str, str]:
        secret = provider.get("api_key")
        return (
            {"Authorization": f"Bearer {secret}"}
            if isinstance(secret, str) and secret
            else {}
        )

    @staticmethod
    def _progress_event(
        provider_id: str,
        model: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        status = str(payload.get("status") or "Working")
        total = OllamaModelManager._integer(payload.get("total"))
        completed = OllamaModelManager._integer(
            payload.get("completed")
        )
        percent = None

        if total and completed is not None:
            percent = max(
                0.0,
                min(100.0, completed / total * 100.0),
            )

        done = status.strip().lower() == "success"
        if done:
            percent = 100.0

        return {
            "type": "done" if done else "progress",
            "provider_id": provider_id,
            "model": model,
            "status": status,
            "digest": payload.get("digest"),
            "total": total,
            "completed": completed,
            "percent": round(percent, 2) if percent is not None else None,
        }

    @staticmethod
    def _error_event(
        provider_id: str,
        model: str,
        message: str,
    ) -> dict[str, Any]:
        return {
            "type": "error",
            "provider_id": provider_id,
            "model": model,
            "status": "error",
            "error": message,
            "total": None,
            "completed": None,
            "percent": None,
        }

    @staticmethod
    def _integer(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return None

    @staticmethod
    def _error_detail(body: bytes) -> str:
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return body.decode("utf-8", errors="replace").strip() or "Unknown error"

        if isinstance(payload, dict):
            detail = payload.get("error") or payload.get("detail")
            if detail:
                return str(detail)
        return str(payload)

    @staticmethod
    def _encode(event: Mapping[str, Any]) -> str:
        return json.dumps(
            dict(event),
            ensure_ascii=False,
            separators=(",", ":"),
        ) + "\n"
