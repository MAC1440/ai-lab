import tempfile
import unittest
from pathlib import Path

from services.unity_docs_service import UnityDocsService


SCRAPED_PAGE = '''---
source_url: "https://docs.unity3d.com/6000.1/Documentation/ScriptReference/AccelerationEvent.html"
title: "AccelerationEvent"
html_length: 368734
---

* Manual
* Scripting API

Version: **Unity 6.1** (6000.1)
* Versions with this page:
* Unity 6.0
* 2022.3

# AccelerationEvent
struct in UnityEngine
/
Implemented in:UnityEngine.InputLegacyModule
Leave feedback
Suggest a change
## Success!
Thank you for helping us improve the quality of Unity Documentation.
Close
## Submission failed
Your suggestion failed.
Cancel
### Description
Structure describing acceleration status of the device.
### Properties
Property | Description
---|---
acceleration | Value of acceleration.
deltaTime | Amount of time passed since last accelerometer measurement.
* * *
Did you find this page useful?
Report a problem on this page

> **[possible repeating chunk]**
'''


class DummyEmbeddingService:
    def __init__(self):
        self.ollama_client = type("Client", (), {"model": "nomic-embed-text"})()

    def embed_texts(self, texts):
        return [[float(index), 1.0] for index, _ in enumerate(texts)]


class DummyChromaService:
    def __init__(self):
        self.collection = type("Collection", (), {"name": "unity_docs"})()
        self.cleared = False
        self.added = []

    def count(self):
        return len(self.added)

    def clear(self):
        self.cleared = True

    def add_chunks(self, **values):
        self.added.extend(values["chunks"])


class UnityDocsServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.page = self.root / "AccelerationEvent.md"
        self.page.write_text(SCRAPED_PAGE, encoding="utf-8")
        self.chroma = DummyChromaService()
        self.service = UnityDocsService(
            embedding_service=DummyEmbeddingService(),
            chroma_service=self.chroma,
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_preview_removes_navigation_and_feedback_noise(self):
        result = self.service.preview(str(self.root), self.page.name)

        cleaned = result["cleaned_content"]
        self.assertNotIn("Versions with this page", cleaned)
        self.assertNotIn("Submission failed", cleaned)
        self.assertNotIn("Did you find this page useful", cleaned)
        self.assertNotIn("possible repeating chunk", cleaned)
        self.assertIn("Structure describing acceleration status", cleaned)
        self.assertIn("deltaTime", cleaned)
        self.assertEqual(result["front_matter"]["title"], "AccelerationEvent")
        self.assertEqual(result["front_matter"]["unity_version"], "Unity 6.1")

    def test_chunks_preserve_source_and_api_metadata(self):
        result = self.service.preview(str(self.root), self.page.name)
        first = result["chunks"][0]

        self.assertIn("Unity API: AccelerationEvent", first["text"])
        self.assertEqual(first["metadata"]["doc_type"], "struct")
        self.assertEqual(
            first["metadata"]["module"],
            "UnityEngine.InputLegacyModule",
        )
        self.assertTrue(first["metadata"]["source_url"].startswith("https://"))

    def test_index_embeds_before_replacing_collection(self):
        events = list(self.service.index_stream(str(self.root), batch_size=2))

        self.assertTrue(self.chroma.cleared)
        self.assertGreater(len(self.chroma.added), 0)
        self.assertEqual(events[-1]["type"], "done")
        self.assertEqual(events[-1]["result"]["document_count"], 1)

    def test_preview_rejects_path_escape(self):
        with self.assertRaisesRegex(ValueError, "inside the source directory"):
            self.service.preview(str(self.root), "../outside.md")


if __name__ == "__main__":
    unittest.main()
