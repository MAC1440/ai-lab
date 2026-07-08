# routers/rag_test.py

from fastapi import APIRouter
from pydantic import BaseModel

from services.chunker import chunk_markdown_by_headings
from services.embeddings import EmbeddingService
from services.chroma_service import ChromaService


router = APIRouter(prefix="/rag-test", tags=["RAG Test"])


embedding_service = EmbeddingService()
chroma_service = ChromaService()


class IndexMarkdownRequest(BaseModel):
    markdown: str
    source: str = "manual_input"

class SearchRequest(BaseModel):
    query: str
    top_k: int = 3


@router.post("/index")
def index_markdown(request: IndexMarkdownRequest):
    chunks = chunk_markdown_by_headings(request.markdown)
    embeddings = embedding_service.embed_texts(chunks)

    metadatas = [
        {
            "source": request.source,
            "chunk_index": i,
        }
        for i in range(len(chunks))
    ]

    result = chroma_service.add_chunks(
        chunks=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    return {
        "chunk_count": len(chunks),
        "result": result,
    }


@router.post("/search")
def search_docs(request: SearchRequest):
    query_embedding = embedding_service.embed_text(request.query)

    results = chroma_service.search(
        query_embedding=query_embedding,
        top_k=request.top_k,
    )

    return results


@router.delete("/clear")
def clear_docs():
    return chroma_service.clear()