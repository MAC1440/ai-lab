import json
import os
from typing import Any, Dict, Iterator, List, Optional

import requests


Message = Dict[str, Any]


class OllamaClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.base_url = (
            base_url
            or os.getenv(
                "OLLAMA_BASE_URL",
                "http://localhost:11434",
            )
        ).rstrip("/")

        self.model = (
            model
            or os.getenv(
                "OLLAMA_MODEL",
                "qwen3:4b",
            )
        )

        self.default_options: Dict[str, Any] = {
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 40,
            "num_predict": 2048,
            "num_ctx": 4096,
        }

    def health(self) -> Dict[str, Any]:
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=30,
            )
        except requests.RequestException as error:
            raise RuntimeError(
                f"Could not connect to Ollama at {self.base_url}: {error}"
            ) from error

        self._raise_ollama_error(response)
        return response.json()

    def _build_messages(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Message]] = None,
    ) -> List[Message]:
        messages: List[Message] = []

        if system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": system_prompt,
                }
            )

        if history:
            messages.extend(history)

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        return messages

    def _raise_ollama_error(
        self,
        response: requests.Response,
    ) -> None:
        if response.ok:
            return

        try:
            error_data = response.json()
            detail = error_data.get(
                "error",
                response.text,
            )
        except ValueError:
            detail = response.text

        raise RuntimeError(
            f"Ollama request failed with status "
            f"{response.status_code}: {detail}"
        )

    def _post_chat(
        self,
        payload: Dict[str, Any],
        *,
        stream: bool = False,
    ) -> requests.Response:
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                stream=stream,
                timeout=360,
            )
        except requests.Timeout as error:
            raise RuntimeError(
                f"Ollama timed out while running model '{self.model}'"
            ) from error
        except requests.ConnectionError as error:
            raise RuntimeError(
                f"Could not connect to Ollama at {self.base_url}. "
                "Confirm that Ollama is running."
            ) from error
        except requests.RequestException as error:
            raise RuntimeError(
                f"Ollama request failed: {error}"
            ) from error

        self._raise_ollama_error(response)
        return response

    def chat(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        history: Optional[List[Message]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": self._build_messages(
                prompt,
                system_prompt,
                history,
            ),
            "stream": False,
            "options": {
                **self.default_options,
                **(options or {}),
            },
        }

        response = self._post_chat(payload)
        data = response.json()

        return data.get("message", {}).get("content", "")

    def stream_chat(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        history: Optional[List[Message]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Iterator[str]:
        payload = {
            "model": self.model,
            "messages": self._build_messages(
                prompt,
                system_prompt,
                history,
            ),
            "stream": True,
            "options": {
                **self.default_options,
                **(options or {}),
            },
        }

        response = self._post_chat(
            payload,
            stream=True,
        )

        for line in response.iter_lines(
            decode_unicode=True,
        ):
            if not line:
                continue

            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue

            delta = chunk.get(
                "message",
                {},
            ).get(
                "content",
                "",
            )

            if delta:
                yield delta

    def embed(
        self,
        texts: List[str],
        model: Optional[str] = None,
    ) -> List[List[float]]:
        payload = {
            "model": (
                model
                or os.getenv(
                    "OLLAMA_EMBEDDING_MODEL",
                    "nomic-embed-text",
                )
            ),
            "input": texts,
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/embed",
                json=payload,
                timeout=120,
            )
        except requests.RequestException as error:
            raise RuntimeError(
                f"Ollama embedding request failed: {error}"
            ) from error

        self._raise_ollama_error(response)

        data = response.json()
        return data.get("embeddings", [])

    def chat_with_tools(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        *,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {
                **self.default_options,
                **(options or {}),
            },
        }

        # Do not send an empty tools array.
        # A normal no-tool agent should behave like ordinary chat.
        if tools:
            payload["tools"] = tools

        response = self._post_chat(payload)
        data = response.json()

        message = data.get("message")

        if not isinstance(message, dict):
            raise RuntimeError(
                "Ollama returned a response without a valid "
                "'message' object"
            )

        return data