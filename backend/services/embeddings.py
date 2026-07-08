from typing import List, Optional

from services.ollama_client import OllamaClient


class EmbeddingService:
    def __init__(self, ollama_client: Optional[OllamaClient] = None):
        self.ollama_client = ollama_client or OllamaClient()

    def embed_text(self, text: str) -> List[float]:
        vectors = self.ollama_client.embed([text])
        return vectors[0] if vectors else []

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return self.ollama_client.embed(texts)
