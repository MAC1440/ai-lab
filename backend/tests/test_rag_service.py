import unittest

from services.rag import RAGService


class DummyEmbeddingService:
    def embed_text(self, text):
        return [1.0, 0.0]

    def embed_texts(self, texts):
        return [
            [1.0, 0.0]
            for _ in texts
        ]


class DummyChromaService:
    def search(
        self,
        query_embedding,
        top_k=3,
    ):
        return {
            "documents": [
                [
                    "chunk one",
                    "chunk two",
                ]
            ],
            "metadatas": [
                [
                    {"source": "doc1"},
                    {"source": "doc2"},
                ]
            ],
            "distances": [
                [
                    0.2,
                    0.8,
                ]
            ],
        }

    def add_chunks(
        self,
        chunks,
        embeddings,
        metadatas=None,
    ):
        return {
            "added": len(chunks),
        }


class DummyOllamaClient:
    def __init__(self):
        # RAGService includes client.model in its response.
        self.model = "dummy-model"

        # These are useful for asserting what RAGService sent.
        self.last_prompt = None
        self.last_system_prompt = None

    def chat(
        self,
        prompt,
        *,
        system_prompt=None,
        history=None,
        options=None,
    ):
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt

        return "answer"

    def stream_chat(
        self,
        prompt,
        *,
        system_prompt=None,
        history=None,
        options=None,
    ):
        yield "answer"


class RAGServiceTests(unittest.TestCase):
    def setUp(self):
        self.ollama_client = DummyOllamaClient()

        self.service = RAGService(
            embedding_service=DummyEmbeddingService(),
            chroma_service=DummyChromaService(),
            ollama_client=self.ollama_client,
        )

    def test_search_and_answer(self):
        results = self.service.search(
            "what is this?",
            top_k=2,
        )

        self.assertEqual(
            results["chunks"],
            [
                "chunk one",
                "chunk two",
            ],
        )
        self.assertEqual(
            results["sources"][0]["source"],
            "doc1",
        )

        answer = self.service.answer(
            "what is this?",
            results,
        )

        self.assertEqual(
            answer["mode"],
            "rag",
        )
        self.assertEqual(
            answer["answer"],
            "answer",
        )
        self.assertEqual(
            answer["model"],
            "dummy-model",
        )
        self.assertEqual(
            answer["sources"][0]["source"],
            "doc1",
        )

        # Confirm the retrieved chunks were placed in the prompt.
        self.assertIn(
            "chunk one",
            self.ollama_client.last_prompt,
        )
        self.assertIn(
            "chunk two",
            self.ollama_client.last_prompt,
        )

        # No agent was provided, so the default prompt is expected.
        self.assertEqual(
            self.ollama_client.last_system_prompt,
            "You are a helpful assistant.",
        )

    def test_search_filters_results_below_threshold(self):
        results = self.service.search(
            "what is this?",
            top_k=2,
            distance_threshold=0.5,
        )

        self.assertEqual(
            results["chunks"],
            ["chunk one"],
        )
        self.assertEqual(
            results["sources"][0]["source"],
            "doc1",
        )
        self.assertEqual(
            results["distances"],
            [0.2],
        )

    def test_normalizes_markdown_like_output(self):
        cleaned = self.service._normalize_response_text(
            "Here is *bold* text\n- bullet point"
        )

        self.assertEqual(
            cleaned,
            "Here is bold text\nbullet point",
        )

    def test_preserves_spacing_for_streaming_chunks(self):
        cleaned = self.service._normalize_response_text(
            " world",
            preserve_outer_whitespace=True,
        )

        self.assertEqual(
            cleaned,
            " world",
        )


if __name__ == "__main__":
    unittest.main()