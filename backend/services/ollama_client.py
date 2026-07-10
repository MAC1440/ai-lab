import json
import os
from typing import Any, Dict, Iterator, List, Optional
from urllib import response

import requests


class OllamaClient:
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen3:4b")
        self.default_options = {
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 40,
            "num_predict": 2048,
            "num_ctx": 2048,
        }

    def health(self) -> Dict[str, Any]:
        response = requests.get(f"{self.base_url}/api/tags", timeout=30)
        response.raise_for_status()
        return response.json()

    def _build_messages(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": prompt})
        return messages
    def _raise_ollama_error(self, response: requests.Response) -> None:
        if response.ok:
             return

        try:
                 error_data = response.json()
                 detail = error_data.get("error", response.text)
        except ValueError:
                detail = response.text

        raise RuntimeError(
                f"Ollama request failed with status {response.status_code}: {detail}"
    )
    def chat(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": self._build_messages(prompt, system_prompt, history),
            "stream": False,
            "options": {**self.default_options, **(options or {})},
        }

        response = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=360,
        )
        self._raise_ollama_error(response)

        data = response.json()
        return data.get("message", {}).get("content", "")

    def stream_chat(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Iterator[str]:
        payload = {
            "model": self.model,
            "messages": self._build_messages(prompt, system_prompt, history),
            "stream": True,
            "options": {**self.default_options, **(options or {})},
        }

        response = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            stream=True,
            timeout=360,
        )
        self._raise_ollama_error(response)

        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue

            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue

            delta = chunk.get("message", {}).get("content", "")

            if delta:
                yield delta

    def embed(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        payload = {
            "model": model or os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
            "input": texts,
        }

        response = requests.post(
            f"{self.base_url}/api/embed",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()

        data = response.json()
        return data.get("embeddings", [])