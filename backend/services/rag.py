import math
import re
from typing import Any, Dict, Iterator, List, Optional

from services.chroma_service import ChromaService
from services.chunker import chunk_markdown_by_headings
from services.embeddings import EmbeddingService
from services.ollama_client import OllamaClient


AgentConfig = Dict[str, Any]


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

        results = self.chroma_service.search(
            query_embedding=query_embedding,
            top_k=top_k,
        )

        retrieved_chunks = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        good_chunks: List[str] = []
        good_sources: List[Dict[str, Any]] = []
        good_distances: List[float] = []

        for chunk, metadata, distance in zip(
            retrieved_chunks,
            metadatas,
            distances,
        ):
            if distance_threshold is None or distance <= distance_threshold:
                good_chunks.append(chunk)
                good_sources.append(metadata or {})
                good_distances.append(distance)

        return {
            "chunks": good_chunks,
            "sources": good_sources,
            "distances": good_distances,
            "distance_threshold": distance_threshold,
        }

    def build_context(
        self,
        query: str,
        documents: List[str],
        top_k: int = 3,
    ) -> str:
        """
        Rank documents supplied directly in a request.

        This is separate from Chroma-based search and is retained for
        backwards compatibility with the older chat endpoint.
        """
        if not documents:
            return ""

        try:
            query_vector = self.embedding_service.embed_text(query)
            document_vectors = self.embedding_service.embed_texts(documents)

            scored_documents = []

            for index, document in enumerate(documents):
                document_vector = document_vectors[index]

                if not document_vector:
                    continue

                score = self._cosine_similarity(
                    query_vector,
                    document_vector,
                )

                scored_documents.append((score, document))

            scored_documents.sort(
                key=lambda item: item[0],
                reverse=True,
            )

            ranked_documents = [
                document
                for _, document in scored_documents[:top_k]
            ]

            if ranked_documents:
                return "\n\n".join(ranked_documents)

        except Exception:
            # Fall back to basic keyword ranking if embedding comparison fails.
            pass

        return self._keyword_context(
            query=query,
            documents=documents,
            top_k=top_k,
        )

    def ask(
        self,
        query: str,
        top_k: int = 3,
        distance_threshold: Optional[float] = 1.0,
        stream: bool = False,
        agent: Optional[AgentConfig] = None,
    ) -> Any:
        search_results = self.search(
            query=query,
            top_k=top_k,
            distance_threshold=distance_threshold,
        )

        return self.answer(
            query=query,
            search_results=search_results,
            stream=stream,
            agent=agent,
        )

    def answer(
        self,
        query: str,
        search_results: Optional[Dict[str, Any]] = None,
        top_k: int = 3,
        stream: bool = False,
        agent: Optional[AgentConfig] = None,
    ) -> Any:
        resolved_results = search_results or self.search(
            query=query,
            top_k=top_k,
        )

        chunks = resolved_results.get("chunks", [])
        sources = resolved_results.get("sources", [])
        distances = resolved_results.get("distances", [])

        # Select the model configured for the requested agent.
        client = self._get_client_for_agent(agent)

        # Select the agent's personality/instructions.
        system_prompt = self._get_system_prompt(agent)

        if chunks:
            context = "\n\n---\n\n".join(chunks)

            prompt = self._build_rag_prompt(
                query=query,
                context=context,
            )

            if stream:
                return self._stream_response(
                    client=client,
                    prompt=prompt,
                    system_prompt=system_prompt,
                )

            answer = client.chat(
                prompt,
                system_prompt=system_prompt,
            )

            return {
                "answer": self._normalize_response_text(answer),
                "mode": "rag",
                "agent_id": self._get_agent_id(agent),
                "model": client.model,
                "sources": sources,
                "distances": distances,
            }

        prompt = self._build_fallback_prompt(query)

        if stream:
            return self._stream_response(
                client=client,
                prompt=prompt,
                system_prompt=system_prompt,
            )

        answer = client.chat(
            prompt,
            system_prompt=system_prompt,
        )

        return {
            "answer": self._normalize_response_text(answer),
            "mode": "model_knowledge",
            "agent_id": self._get_agent_id(agent),
            "model": client.model,
            "sources": [],
            "distances": [],
        }

    def index_documents(
        self,
        documents: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        all_chunks: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for document in documents:
            chunks = self.chunker(document["content"])

            for chunk_index, chunk in enumerate(chunks):
                all_chunks.append(chunk)

                metadatas.append(
                    {
                        "source": document["name"],
                        "chunk_index": chunk_index,
                    }
                )

        if not all_chunks:
            return {
                "document_count": len(documents),
                "chunk_count": 0,
                "result": {
                    "added": 0,
                    "ids": [],
                },
            }

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

    def _get_client_for_agent(
        self,
        agent: Optional[AgentConfig],
    ) -> OllamaClient:
        """
        Return a client configured with the agent's model.

        If no agent or model is supplied, reuse the default client that was
        configured from the environment.
        """
        if not agent:
            return self.ollama_client

        model = agent.get("model")

        if not model or model == self.ollama_client.model:
            return self.ollama_client

        return OllamaClient(
            base_url=self.ollama_client.base_url,
            model=model,
        )

    def _get_system_prompt(
        self,
        agent: Optional[AgentConfig],
    ) -> str:
        if not agent:
            return "You are a helpful assistant."

        return agent.get(
            "system_prompt",
            "You are a helpful assistant.",
        )

    def _get_agent_id(
        self,
        agent: Optional[AgentConfig],
    ) -> str:
        if not agent:
            return "default"

        return agent.get("id", "default")

    def _build_rag_prompt(
        self,
        query: str,
        context: str,
    ) -> str:
        return f"""Use the retrieved documents to answer the user's question.

Instructions:
- Prefer the retrieved context whenever it contains the answer.
- Do not invent facts that are not supported by the context.
- If the context is insufficient, clearly state that limitation.
- Do not expose internal reasoning or thinking.
- Give only the final answer.
- Keep the response concise and natural.

Retrieved context:
{context}

Question:
{query}
"""

    def _build_fallback_prompt(self, query: str) -> str:
        return f"""No sufficiently relevant local documents were retrieved.

Answer the user's question from your general trained knowledge.

Instructions:
- Clearly state that no relevant local documents were found.
- Clearly distinguish general model knowledge from local documentation.
- Do not expose internal reasoning or thinking.
- Give only the final answer.
- Keep the response concise and natural.

Question:
{query}
"""

    def _stream_response(
        self,
        client: OllamaClient,
        prompt: str,
        system_prompt: str,
    ) -> Iterator[str]:
        """
        Stream directly from the model selected by the agent.

        We avoid running regex normalization on individual chunks because
        markdown symbols may be split across separate streamed chunks.
        """
        yield from client.stream_chat(
            prompt,
            system_prompt=system_prompt,
        )

    def _normalize_response_text(
        self,
        text: str,
        preserve_outer_whitespace: bool = False,
    ) -> str:
        if not text:
            return ""

        normalized = text.replace("\r\n", "\n")
        normalized = re.sub(
            r"(?<!\*)\*\*(.*?)\*\*(?!\*)",
            r"\1",
            normalized,
        )
        normalized = re.sub(
            r"(?<!\*)\*(.*?)\*(?!\*)",
            r"\1",
            normalized,
        )
        normalized = re.sub(
            r"(?<!_)__(.*?)__(?!_)",
            r"\1",
            normalized,
        )
        normalized = re.sub(
            r"(?<!_)_(.*?)_(?!_)",
            r"\1",
            normalized,
        )
        normalized = re.sub(r"`([^`]*)`", r"\1", normalized)
        normalized = re.sub(
            r"^\s{0,3}#{1,6}\s*",
            "",
            normalized,
            flags=re.MULTILINE,
        )
        normalized = re.sub(
            r"^\s*[-*+]\s+",
            "",
            normalized,
            flags=re.MULTILINE,
        )
        normalized = re.sub(
            r"^\s*\d+\.\s+",
            "",
            normalized,
            flags=re.MULTILINE,
        )
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)

        if preserve_outer_whitespace:
            return normalized

        return normalized.strip()

    def _keyword_context(
        self,
        query: str,
        documents: List[str],
        top_k: int,
    ) -> str:
        query_tokens = set(self._tokenize(query))
        scored_documents = []

        for document in documents:
            document_tokens = self._tokenize(document)

            if not document_tokens:
                continue

            overlap = len(
                query_tokens.intersection(document_tokens)
            )

            scored_documents.append(
                (overlap, document)
            )

        scored_documents.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        ranked_documents = [
            document
            for _, document in scored_documents[:top_k]
        ]

        return "\n\n".join(ranked_documents)

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\w+", text.lower())

    def _cosine_similarity(
        self,
        left: List[float],
        right: List[float],
    ) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0

        dot_product = sum(
            left_value * right_value
            for left_value, right_value in zip(left, right)
        )

        left_norm = math.sqrt(
            sum(value * value for value in left)
        )

        right_norm = math.sqrt(
            sum(value * value for value in right)
        )

        if left_norm == 0 or right_norm == 0:
            return 0.0

        return dot_product / (left_norm * right_norm)