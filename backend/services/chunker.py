# services/chunker.py

from typing import List


def chunk_markdown_by_headings(markdown_text: str) -> List[str]:
    chunks = []
    current_chunk = []

    for line in markdown_text.splitlines():
        if line.startswith("#") and current_chunk:
            chunks.append("\n".join(current_chunk).strip())
            current_chunk = [line]
        else:
            current_chunk.append(line)

    if current_chunk:
        chunks.append("\n".join(current_chunk).strip())

    return [chunk for chunk in chunks if chunk]