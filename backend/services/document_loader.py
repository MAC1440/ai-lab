from pathlib import Path


class DocumentLoader:
    def load_markdown_documents(self, folder: str = "unity_docs") -> list:
        docs = []
        path = Path(__file__).resolve().parent.parent / folder
        for file in path.glob("*.md"):
            docs.append({
                "name": file.name,
                "content": file.read_text(encoding="utf-8"),
            })
        return docs
