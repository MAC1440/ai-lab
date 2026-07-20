import tempfile
import unittest
from pathlib import Path

from services.knowledge_source_service import KnowledgeSourceService


class FakeEmbeddings:
    def embed_texts(self, texts):
        return [[float(len(text))] for text in texts]


class FakeChroma:
    def __init__(self):
        self.rows = {}

    def count(self):
        return len(self.rows)

    def delete_where(self, where):
        source_id = where["knowledge_source"]
        self.rows = {
            key: value for key, value in self.rows.items()
            if value["metadata"].get("knowledge_source") != source_id
        }

    def add_chunks(self, chunks, embeddings, metadatas, ids):
        for chunk, embedding, metadata, item_id in zip(chunks, embeddings, metadatas, ids):
            self.rows[item_id] = {"chunk": chunk, "embedding": embedding, "metadata": metadata}


class KnowledgeSourceServiceTests(unittest.TestCase):
    def test_new_source_appends_and_same_id_replaces_only_itself(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source_a = root / "a"
            source_b = root / "b"
            source_a.mkdir()
            source_b.mkdir()
            (source_a / "app.py").write_text("print('a')", encoding="utf-8")
            (source_b / "README.md").write_text("# B", encoding="utf-8")
            chroma = FakeChroma()
            service = KnowledgeSourceService(root / "catalog.json", FakeEmbeddings(), chroma)

            list(service.index_stream(source_id="a", name="A", source_directory=str(source_a)))
            a_count = chroma.count()
            list(service.index_stream(source_id="b", name="B", source_directory=str(source_b)))
            self.assertGreater(chroma.count(), a_count)

            (source_a / "app.py").write_text("print('updated')", encoding="utf-8")
            list(service.index_stream(source_id="a", name="A", source_directory=str(source_a)))
            sources = {item["id"]: item for item in service.status()["sources"]}
            self.assertEqual(set(sources), {"a", "b"})
            self.assertTrue(any(row["metadata"]["knowledge_source"] == "b" for row in chroma.rows.values()))

    def test_generated_folders_are_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "node_modules").mkdir()
            (root / "node_modules" / "ignored.js").write_text("ignored", encoding="utf-8")
            (root / "main.ts").write_text("export const value = 1", encoding="utf-8")
            chroma = FakeChroma()
            service = KnowledgeSourceService(root / "catalog.json", FakeEmbeddings(), chroma)
            result = list(service.index_stream(source_id="web", name="Web", source_directory=str(root)))[-1]
            self.assertEqual(result["result"]["document_count"], 1)


if __name__ == "__main__":
    unittest.main()
