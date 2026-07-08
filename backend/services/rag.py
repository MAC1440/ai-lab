import math
import re
from typing import Any, Dict, List, Optional

from services.chroma_service import ChromaService
from services.chunker import chunk_markdown_by_headings
from services.embeddings import EmbeddingService
from services.ollama_client import OllamaClient


class RAGService:
    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        chroma_service: Optional[ChromaService] = None,
        ollama_client: Optional[OllamaClient] = None,
        chunker=None,
    ):
        self.embedding_service = embedding_service or EmbeddingService()
        self.chroma_service = chroma_service or ChromaService()
        self.ollama_client = ollama_client or OllamaClient()
        self.chunker = chunker or chunk_markdown_by_headings

    def search(
        self,
        query: str,
        top_k: int = 3,
        distance_threshold: Optional[float] = 1.0,
    ) -> Dict[str, Any]:
        query_embedding = self.embedding_service.embed_text(query)
        results = self.chroma_service.search(query_embedding=query_embedding, top_k=top_k)

        retrieved_chunks = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        good_chunks = []
        good_sources = []
        for chunk, metadata, distance in zip(retrieved_chunks, metadatas, distances):
            if distance_threshold is None or distance <= distance_threshold:
                good_chunks.append(chunk)
                good_sources.append(metadata or {})

        return {
            "chunks": good_chunks,
            "sources": good_sources,
            "distance_threshold": distance_threshold,
        }

    def build_context(self, query: str, documents: List[str], top_k: int = 3) -> str:
        if not documents:
            return ""

        if self.embedding_service:
            try:
                query_vector = self.embedding_service.embed_text(query)
                doc_vectors = self.embedding_service.embed_texts(documents)
                scored_docs = []
                for idx, doc in enumerate(documents):
                    if not doc_vectors[idx]:
                        continue
                    score = self._cosine_similarity(query_vector, doc_vectors[idx])
                    scored_docs.append((score, doc))

                scored_docs.sort(key=lambda item: item[0], reverse=True)
                ranked_docs = [doc for _, doc in scored_docs[:top_k]]
                if ranked_docs:
                    return "\n\n".join(ranked_docs)
            except Exception:
                pass

        return self._keyword_context(query, documents, top_k)

    def ask(
        self,
        query: str,
        top_k: int = 3,
        distance_threshold: Optional[float] = 1.0,
        stream: bool = False,
    ) -> Any:
        search_results = self.search(query, top_k=top_k, distance_threshold=distance_threshold)
        return self.answer(query, search_results, stream=stream)

    def answer(
        self,
        query: str,
        search_results: Optional[Dict[str, Any]] = None,
        top_k: int = 3,
        stream: bool = False,
    ) -> Any:
        resolved_results = search_results or self.search(query, top_k=top_k)
        chunks = resolved_results.get("chunks", [])
        sources = resolved_results.get("sources", [])

        if chunks:
            context = "\n\n---\n\n".join(chunks)
            prompt = self._build_rag_prompt(query, context)
            if stream:
                return self._stream_normalized_response(prompt)
            answer = self.ollama_client.chat(prompt)
            return {
                "answer": self._normalize_response_text(answer),
                "mode": "rag",
                "sources": sources,
            }

        prompt = self._build_fallback_prompt(query)
        if stream:
            return self._stream_normalized_response(prompt)
        answer = self.ollama_client.chat(prompt)
        return {
            "answer": self._normalize_response_text(answer),
            "mode": "model_knowledge",
            "sources": [],
        }

    def index_documents(self, documents: List[Dict[str, str]]) -> Dict[str, Any]:
        all_chunks = []
        metadatas = []

        for doc in documents:
            chunks = self.chunker(doc["content"])
            for chunk_index, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                metadatas.append({
                    "source": doc["name"],
                    "chunk_index": chunk_index,
                })

        embeddings = self.embedding_service.embed_texts(all_chunks)
        result = self.chroma_service.add_chunks(
            chunks=all_chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        return {
            "document_count": len(documents),
            "chunk_count": len(all_chunks),
            "result": result,
        }

    def _build_rag_prompt(self, query: str, context: str) -> str:
        return f"""You are a careful assistant grounded in the retrieved documents.

Instructions:
- Answer using only the retrieved context whenever it is relevant.
- If the context is insufficient, say that you do not have enough information from the documents.
- Do not claim facts that are not present in the context.
- Keep the answer concise, direct, and written in plain, natural language.
- Avoid markdown formatting such as asterisks, underscores, headings, or code fences.
- Use short paragraphs or simple bullet points only when they make the answer easier to read.

Retrieved context:
{context}

Question:
{query}
"""

    def _build_fallback_prompt(self, query: str) -> str:
        return f"""You are a helpful assistant.

Instructions:
- Answer from general knowledge when no relevant local documents were retrieved.
- Clearly say that the answer is based on general knowledge rather than the local documents.
- Keep the answer concise and avoid pretending the documents support the claim.
- Write in plain, natural language without markdown symbols or heavy formatting.

Question:
{query}
"""

    def _stream_normalized_response(self, prompt: str):
        for chunk in self.ollama_client.stream_chat(prompt):
            yield self._normalize_response_text(chunk, preserve_outer_whitespace=True)

    def _normalize_response_text(self, text: str, preserve_outer_whitespace: bool = False) -> str:
        if not text:
            return ""

        normalized = text.replace("\r\n", "\n")
        normalized = re.sub(r"(?<!\*)\*\*(.*?)\*\*(?!\*)", r"\1", normalized)
        normalized = re.sub(r"(?<!\*)\*(.*?)\*(?!\*)", r"\1", normalized)
        normalized = re.sub(r"(?<!_)__(.*?)__(?!_)", r"\1", normalized)
        normalized = re.sub(r"(?<!_)_(.*?)_(?!_)", r"\1", normalized)
        normalized = re.sub(r"`([^`]*)`", r"\1", normalized)
        normalized = re.sub(r"^\s{0,3}#{1,6}\s*", "", normalized, flags=re.M)
        normalized = re.sub(r"^\s*[-*+]\s+", "", normalized, flags=re.M)
        normalized = re.sub(r"^\s*\d+\.\s+", "", normalized, flags=re.M)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)

        if preserve_outer_whitespace:
            return normalized

        return normalized.strip()

    def _keyword_context(self, query: str, documents: List[str], top_k: int) -> str:
        query_tokens = set(self._tokenize(query))
        scored_docs = []
        for doc in documents:
            doc_tokens = self._tokenize(doc)
            if not doc_tokens:
                continue
            overlap = len(query_tokens.intersection(doc_tokens))
            scored_docs.append((overlap, doc))

        scored_docs.sort(key=lambda item: item[0], reverse=True)
        ranked_docs = [doc for _, doc in scored_docs[:top_k]]
        return "\n\n".join(ranked_docs)

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\w+", text.lower())

    def _cosine_similarity(self, left: List[float], right: List[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)
