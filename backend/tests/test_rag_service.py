import unittest

from services.rag import RAGService


class DummyEmbeddingService:
    def embed_text(self, text):
        return [1.0, 0.0]

    def embed_texts(self, texts):
        return [[1.0, 0.0] for _ in texts]


class DummyChromaService:
    def search(self, query_embedding, top_k=3):
        return {
            "documents": [["chunk one", "chunk two"]],
            "metadatas": [[{"source": "doc1"}, {"source": "doc2"}]],
            "distances": [[0.2, 0.8]],
        }

    def add_chunks(self, chunks, embeddings, metadatas=None):
        return {"added": len(chunks)}


class DummyOllamaClient:
    def chat(self, prompt):
        return "answer"


class RAGServiceTests(unittest.TestCase):
    def test_search_and_answer(self):
        service = RAGService(
            embedding_service=DummyEmbeddingService(),
            chroma_service=DummyChromaService(),
            ollama_client=DummyOllamaClient(),
        )

        results = service.search("what is this?", top_k=2)

        self.assertEqual(results["chunks"], ["chunk one", "chunk two"])
        self.assertEqual(results["sources"][0]["source"], "doc1")

        answer = service.answer("what is this?", results)

        self.assertEqual(answer["mode"], "rag")
        self.assertEqual(answer["answer"], "answer")
        self.assertEqual(answer["sources"][0]["source"], "doc1")

    def test_search_filters_results_below_threshold(self):
        service = RAGService(
            embedding_service=DummyEmbeddingService(),
            chroma_service=DummyChromaService(),
            ollama_client=DummyOllamaClient(),
        )

        results = service.search("what is this?", top_k=2, distance_threshold=0.5)

        self.assertEqual(results["chunks"], ["chunk one"])
        self.assertEqual(results["sources"][0]["source"], "doc1")

    def test_normalizes_markdown_like_output(self):
        service = RAGService(
            embedding_service=DummyEmbeddingService(),
            chroma_service=DummyChromaService(),
            ollama_client=DummyOllamaClient(),
        )

        cleaned = service._normalize_response_text("Here is *bold* text\n- bullet point")

        self.assertEqual(cleaned, "Here is bold text\nbullet point")

    def test_preserves_spacing_for_streaming_chunks(self):
        service = RAGService(
            embedding_service=DummyEmbeddingService(),
            chroma_service=DummyChromaService(),
            ollama_client=DummyOllamaClient(),
        )

        cleaned = service._normalize_response_text(" world", preserve_outer_whitespace=True)

        self.assertEqual(cleaned, " world")


if __name__ == "__main__":
    unittest.main()
