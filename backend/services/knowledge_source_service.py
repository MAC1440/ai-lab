from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

TEXT_EXTENSIONS = {
    ".c", ".cc", ".cpp", ".cs", ".css", ".go", ".h", ".hpp", ".html",
    ".java", ".js", ".json", ".jsx", ".kt", ".md", ".markdown", ".php",
    ".ps1", ".py", ".rb", ".rs", ".sh", ".sql", ".svelte", ".swift",
    ".toml", ".ts", ".tsx", ".txt", ".vue", ".xml", ".yaml", ".yml",
}
IGNORED_PARTS = {
    ".git", ".idea", ".next", ".venv", ".vs", ".vscode", "Library",
    "Temp", "build", "dist", "node_modules", "obj", "venv",
}


class KnowledgeSourceService:
    """Incrementally adds independent local folders to the shared RAG index."""

    def __init__(
        self,
        catalog_path: Path,
        embedding_service: Any | None = None,
        chroma_service: Any | None = None,
        *,
        max_file_bytes: int = 2_000_000,
        chunk_characters: int = 2200,
        overlap_characters: int = 200,
    ) -> None:
        self.catalog_path = catalog_path
        if embedding_service is None:
            from services.embeddings import EmbeddingService
            embedding_service = EmbeddingService()
        if chroma_service is None:
            from services.chroma_service import ChromaService
            chroma_service = ChromaService()
        self.embedding_service = embedding_service
        self.chroma_service = chroma_service
        self.max_file_bytes = max_file_bytes
        self.chunk_characters = chunk_characters
        self.overlap_characters = overlap_characters
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)

    def status(self) -> dict[str, Any]:
        return {
            "total_chunk_count": self.chroma_service.count(),
            "embedding_model": os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
            "sources": self._load(),
        }

    def remove(self, source_id: str) -> dict[str, Any]:
        sources = self._load()
        if not any(item["id"] == source_id for item in sources):
            raise ValueError(f"Knowledge source '{source_id}' was not found")
        self.chroma_service.delete_where({"knowledge_source": source_id})
        self._save([item for item in sources if item["id"] != source_id])
        return {"removed": True, "source_id": source_id}

    def index_stream(
        self,
        *,
        source_id: str,
        name: str,
        source_directory: str,
        batch_size: int = 24,
    ) -> Iterator[dict[str, Any]]:
        clean_id = self._clean_id(source_id)
        root = Path(source_directory).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f"Knowledge folder does not exist: {root}")
        paths = sorted(
            path for path in root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in TEXT_EXTENSIONS
            and not IGNORED_PARTS.intersection(path.relative_to(root).parts)
        )
        if not paths:
            raise ValueError(f"No supported text or code files found under: {root}")
        yield {"type": "status", "stage": "scanning", "message": f"Found {len(paths)} files", "file_count": len(paths)}

        chunks: list[str] = []
        metadatas: list[dict[str, Any]] = []
        ids: list[str] = []
        skipped: list[dict[str, str]] = []
        for index, path in enumerate(paths, start=1):
            relative = path.relative_to(root).as_posix()
            try:
                if path.stat().st_size > self.max_file_bytes:
                    raise ValueError("File exceeds size limit")
                content = path.read_text(encoding="utf-8")
                for chunk_index, chunk in enumerate(self._chunks(content)):
                    header = f"Knowledge source: {name}\nFile: {relative}\n\n"
                    text = header + chunk
                    identity = f"{clean_id}|{relative}|{chunk_index}|{hashlib.sha256(content.encode()).hexdigest()}"
                    chunks.append(text)
                    ids.append(hashlib.sha256(identity.encode()).hexdigest())
                    metadatas.append({
                        "knowledge_source": clean_id,
                        "knowledge_name": name.strip(),
                        "source": relative,
                        "chunk_index": chunk_index,
                        "file_extension": path.suffix.lower(),
                    })
            except (OSError, UnicodeError, ValueError) as error:
                skipped.append({"source": relative, "reason": str(error)})
            if index % 100 == 0 or index == len(paths):
                yield {"type": "progress", "stage": "reading", "completed": index, "total": len(paths), "chunk_count": len(chunks), "skipped_count": len(skipped)}

        if not chunks:
            raise ValueError("No indexable content was produced")

        embedded: list[list[float]] = []
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            embedded.extend(self.embedding_service.embed_texts(batch))
            yield {"type": "progress", "stage": "embedding", "completed": min(start + len(batch), len(chunks)), "total": len(chunks)}
        if len(embedded) != len(chunks):
            raise RuntimeError("Embedding service returned an unexpected vector count")

        # Replacement is scoped to this source only. Unity and every other
        # source remain untouched.
        try:
            self.chroma_service.delete_where({"knowledge_source": clean_id})
        except Exception:
            pass
        for start in range(0, len(chunks), 5000):
            end = start + 5000
            self.chroma_service.add_chunks(chunks[start:end], embedded[start:end], metadatas[start:end], ids[start:end])

        source = {
            "id": clean_id,
            "name": name.strip(),
            "source_directory": str(root),
            "document_count": len(paths) - len(skipped),
            "chunk_count": len(chunks),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        sources = [item for item in self._load() if item["id"] != clean_id]
        self._save([*sources, source])
        yield {"type": "done", "result": {**source, "skipped_count": len(skipped), "skipped": skipped[:100]}}

    def _chunks(self, content: str) -> list[str]:
        clean = content.replace("\r\n", "\n").strip()
        if not clean:
            return []
        result: list[str] = []
        start = 0
        while start < len(clean):
            end = min(len(clean), start + self.chunk_characters)
            if end < len(clean):
                boundary = clean.rfind("\n", start, end)
                if boundary > start + self.chunk_characters // 2:
                    end = boundary
            result.append(clean[start:end].strip())
            if end >= len(clean):
                break
            start = max(start + 1, end - self.overlap_characters)
        return [item for item in result if item]

    @staticmethod
    def _clean_id(value: str) -> str:
        clean = "".join(character.lower() if character.isalnum() else "-" for character in value.strip())
        clean = "-".join(part for part in clean.split("-") if part)
        if not clean:
            raise ValueError("source_id must contain letters or numbers")
        return clean[:80]

    def _load(self) -> list[dict[str, Any]]:
        if not self.catalog_path.exists():
            return []
        try:
            value = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            return value if isinstance(value, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _save(self, value: list[dict[str, Any]]) -> None:
        temporary = self.catalog_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
        temporary.replace(self.catalog_path)
