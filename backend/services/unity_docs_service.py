from __future__ import annotations

import hashlib
import os
import pickle
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from services.chroma_service import ChromaService
from services.embeddings import EmbeddingService


FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
UNITY_VERSION = re.compile(r"Version:\s*\*\*([^*]+)\*\*", re.IGNORECASE)
IMPLEMENTED_IN = re.compile(r"Implemented in:\s*([^\n]+)", re.IGNORECASE)
API_DECLARATION = re.compile(
    r"^(class|struct|interface|enum|delegate)\s+in\s+([^\n]+)$",
    re.IGNORECASE | re.MULTILINE,
)

NOISE_LINES = {
    "Leave feedback",
    "Suggest a change",
    "Your name Your email Suggestion* Submit suggestion",
    "Cancel",
    "Close",
    "> **[possible repeating chunk]**",
}


@dataclass(frozen=True)
class UnityChunk:
    text: str
    metadata: dict[str, Any]
    chunk_id: str


@dataclass(frozen=True)
class ParsedUnityDocument:
    source: str
    cleaned_content: str
    front_matter: dict[str, Any]
    chunks: list[UnityChunk]


class UnityDocsService:
    """Clean scraped Unity pages and rebuild the Unity RAG collection."""

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        chroma_service: ChromaService | None = None,
        *,
        max_file_bytes: int = 5_000_000,
        max_chunk_characters: int = 2400,
    ) -> None:
        self.embedding_service = embedding_service or EmbeddingService()
        self.chroma_service = chroma_service or ChromaService()
        self.max_file_bytes = max_file_bytes
        self.max_chunk_characters = max_chunk_characters

    def status(self) -> dict[str, Any]:
        return {
            "collection": self.chroma_service.collection.name,
            "chunk_count": self.chroma_service.count(),
            "embedding_model": os.getenv(
                "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"
            ),
        }

    def preview(self, source_directory: str, relative_file: str) -> dict[str, Any]:
        root = self._source_directory(source_directory)
        path = self._resolve_inside(root, relative_file)
        document = self.parse_file(path, root)
        return {
            "source": document.source,
            "front_matter": document.front_matter,
            "cleaned_content": document.cleaned_content,
            "original_characters": path.stat().st_size,
            "cleaned_characters": len(document.cleaned_content),
            "chunk_count": len(document.chunks),
            "chunks": [
                {"text": item.text, "metadata": item.metadata}
                for item in document.chunks
            ],
        }

    def index_stream(
        self,
        source_directory: str,
        *,
        batch_size: int = 24,
    ) -> Iterator[dict[str, Any]]:
        root = self._source_directory(source_directory)
        paths = sorted(
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".md", ".markdown", ".txt"}
        )
        if not paths:
            raise ValueError(f"No Markdown files found under: {root}")

        yield {
            "type": "status",
            "stage": "scanning",
            "message": f"Found {len(paths)} Markdown files",
            "file_count": len(paths),
        }

        all_chunks: list[UnityChunk] = []
        skipped: list[dict[str, str]] = []
        for index, path in enumerate(paths, start=1):
            try:
                if path.stat().st_size > self.max_file_bytes:
                    raise ValueError(
                        f"File exceeds {self.max_file_bytes:,} byte limit"
                    )
                document = self.parse_file(path, root)
                if not document.chunks:
                    raise ValueError("No useful Unity documentation remained")
                all_chunks.extend(document.chunks)
            except (OSError, UnicodeError, ValueError) as error:
                skipped.append(
                    {"source": path.relative_to(root).as_posix(), "reason": str(error)}
                )
            if index % 100 == 0 or index == len(paths):
                yield {
                    "type": "progress",
                    "stage": "cleaning",
                    "completed": index,
                    "total": len(paths),
                    "chunk_count": len(all_chunks),
                    "skipped_count": len(skipped),
                }

        if not all_chunks:
            raise ValueError("No indexable Unity documentation was produced")

        texts = [item.text for item in all_chunks]
        with tempfile.TemporaryDirectory(prefix="ai-lab-unity-index-") as folder:
            spool = Path(folder)
            batches: list[tuple[int, int, Path]] = []
            for start in range(0, len(texts), batch_size):
                batch = texts[start:start + batch_size]
                embeddings = self.embedding_service.embed_texts(batch)
                if len(embeddings) != len(batch):
                    raise RuntimeError(
                        f"Ollama returned {len(embeddings)} embeddings for "
                        f"a batch of {len(batch)} chunks"
                    )
                batch_path = spool / f"{start:09d}.pickle"
                with batch_path.open("wb") as stream:
                    pickle.dump(embeddings, stream, protocol=pickle.HIGHEST_PROTOCOL)
                batches.append((start, len(batch), batch_path))
                yield {
                    "type": "progress",
                    "stage": "embedding",
                    "completed": min(start + len(batch), len(texts)),
                    "total": len(texts),
                }

            # Replacement happens only after every embedding batch succeeds.
            self.chroma_service.clear()
            for start, length, batch_path in batches:
                items = all_chunks[start:start + length]
                with batch_path.open("rb") as stream:
                    embeddings = pickle.load(stream)  # noqa: S301 - trusted temp file
                self.chroma_service.add_chunks(
                    chunks=[item.text for item in items],
                    embeddings=embeddings,
                    metadatas=[item.metadata for item in items],
                    ids=[item.chunk_id for item in items],
                )

        yield {
            "type": "done",
            "result": {
                "source_directory": str(root),
                "document_count": len(paths) - len(skipped),
                "skipped_count": len(skipped),
                "chunk_count": len(all_chunks),
                "skipped": skipped[:100],
                "skipped_truncated": len(skipped) > 100,
            },
        }

    def parse_file(self, path: Path, root: Path | None = None) -> ParsedUnityDocument:
        raw = path.read_text(encoding="utf-8")
        front_matter, body = self._parse_front_matter(raw)
        source = path.relative_to(root).as_posix() if root else path.name
        cleaned = self._clean_body(body, front_matter)
        chunks = self._chunks(cleaned, front_matter, source)
        return ParsedUnityDocument(
            source=source,
            cleaned_content=cleaned,
            front_matter=front_matter,
            chunks=chunks,
        )

    @staticmethod
    def _parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        match = FRONT_MATTER.match(normalized)
        if not match:
            return {}, normalized
        values: dict[str, Any] = {}
        for raw_line in match.group(1).splitlines():
            if ":" not in raw_line:
                continue
            key, value = raw_line.split(":", 1)
            clean = value.strip().strip('"').strip("'")
            values[key.strip()] = int(clean) if clean.isdigit() else clean
        return values, normalized[match.end():]

    def _clean_body(self, body: str, metadata: dict[str, Any]) -> str:
        version_match = UNITY_VERSION.search(body)
        if version_match:
            metadata.setdefault("unity_version", version_match.group(1).strip())

        title = str(metadata.get("title", "")).strip()
        title_pattern = (
            re.compile(rf"^#\s+{re.escape(title)}\s*$", re.MULTILINE)
            if title else None
        )
        first_title = title_pattern.search(body) if title_pattern else None
        if first_title is None:
            first_title = re.search(r"^#\s+.+$", body, re.MULTILINE)
        useful = body[first_title.start():] if first_title else body

        useful = re.sub(
            r"## Success!.*?Close\s*",
            "",
            useful,
            flags=re.DOTALL,
        )
        useful = re.sub(
            r"## Submission failed.*?Cancel\s*",
            "",
            useful,
            flags=re.DOTALL,
        )
        footer = re.search(
            r"^Did you find this page useful\?",
            useful,
            re.MULTILINE,
        )
        if footer:
            useful = useful[:footer.start()]

        lines = []
        for line in useful.splitlines():
            stripped = line.strip()
            if stripped in NOISE_LINES:
                continue
            lines.append(line.rstrip())
        useful = "\n".join(lines)
        useful = re.sub(r"\n[ \t]+\n", "\n\n", useful)
        useful = re.sub(r"\n{3,}", "\n\n", useful).strip()
        return useful

    def _chunks(
        self,
        content: str,
        metadata: dict[str, Any],
        source: str,
    ) -> list[UnityChunk]:
        if not content.strip():
            return []
        title = str(metadata.get("title") or self._title_from_content(content))
        version = str(metadata.get("unity_version", ""))
        module_match = IMPLEMENTED_IN.search(content)
        declaration_match = API_DECLARATION.search(content)
        module = module_match.group(1).strip() if module_match else ""
        doc_type = declaration_match.group(1).lower() if declaration_match else ""
        namespace = declaration_match.group(2).strip() if declaration_match else ""
        source_url = str(metadata.get("source_url", ""))

        matches = list(HEADING.finditer(content))
        sections: list[tuple[str, str]] = []
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            sections.append((match.group(2).strip(), content[start:end].strip()))
        if not sections:
            sections = [(title, content)]

        context_lines = [f"Unity API: {title}"]
        if version:
            context_lines.append(f"Unity version: {version}")
        if doc_type:
            context_lines.append(f"Kind: {doc_type}")
        if namespace:
            context_lines.append(f"Namespace: {namespace}")
        if module:
            context_lines.append(f"Module: {module}")
        if source_url:
            context_lines.append(f"Source: {source_url}")
        context = "\n".join(context_lines)

        chunks: list[UnityChunk] = []
        for heading, section in sections:
            for part in self._split_to_limit(section):
                text = f"{context}\n\n{part}".strip()
                chunk_index = len(chunks)
                identity = f"{source_url or source}|{chunk_index}|{heading}"
                chunk_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
                chunk_metadata = {
                    "source": source,
                    "source_url": source_url,
                    "title": title,
                    "unity_version": version,
                    "doc_type": doc_type,
                    "module": module,
                    "heading": heading,
                    "chunk_index": chunk_index,
                }
                chunks.append(UnityChunk(text, chunk_metadata, chunk_id))
        return chunks

    def _split_to_limit(self, text: str) -> list[str]:
        if len(text) <= self.max_chunk_characters:
            return [text]
        paragraphs = re.split(r"\n\s*\n", text)
        parts: list[str] = []
        current = ""
        for paragraph in paragraphs:
            units = self._hard_split(paragraph)
            for unit in units:
                candidate = f"{current}\n\n{unit}".strip() if current else unit
                if current and len(candidate) > self.max_chunk_characters:
                    parts.append(current)
                    current = unit
                else:
                    current = candidate
        if current:
            parts.append(current)
        return parts

    def _hard_split(self, text: str) -> list[str]:
        if len(text) <= self.max_chunk_characters:
            return [text]
        if "\n" not in text:
            return [
                text[index:index + self.max_chunk_characters]
                for index in range(0, len(text), self.max_chunk_characters)
            ]
        lines = text.splitlines()
        parts: list[str] = []
        current = ""
        for line in lines:
            candidate = f"{current}\n{line}".strip() if current else line
            if current and len(candidate) > self.max_chunk_characters:
                parts.append(current)
                current = line
            else:
                current = candidate
        if current:
            parts.append(current)
        return parts

    @staticmethod
    def _title_from_content(content: str) -> str:
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        return match.group(1).strip() if match else "Unity documentation"

    @staticmethod
    def _source_directory(value: str) -> Path:
        path = Path(value).expanduser().resolve()
        if not path.exists():
            raise ValueError(f"Source directory does not exist: {path}")
        if not path.is_dir():
            raise ValueError(f"Source path is not a directory: {path}")
        return path

    @staticmethod
    def _resolve_inside(root: Path, relative_file: str) -> Path:
        path = (root / relative_file).resolve()
        try:
            path.relative_to(root)
        except ValueError as error:
            raise ValueError("Preview file must remain inside the source directory") from error
        if not path.is_file():
            raise ValueError(f"Preview file does not exist: {relative_file}")
        return path
