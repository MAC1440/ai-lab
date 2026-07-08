from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.document_loader import DocumentLoader
from services.rag import RAGService


class DocumentSearchRequest(BaseModel):
    query: str
    top_k: int = 3
    stream: bool = False


router = APIRouter(prefix="/documents", tags=["Docs Test"])
loader = DocumentLoader()
rag_service = RAGService()


@router.get("/")
def list_documents():
    documents = loader.load_markdown_documents()
    return {"documents": documents}


@router.post("/ask")
def ask_question(request: DocumentSearchRequest):
    if request.stream:
        return StreamingResponse(
            rag_service.ask(request.query, top_k=request.top_k, stream=True),
            media_type="text/plain",
        )

    results = rag_service.search(request.query, top_k=request.top_k)
    return rag_service.answer(request.query, results)


@router.get("/index")
def index_documents():
    documents = loader.load_markdown_documents()
    return rag_service.index_documents(documents)


@router.post("/search")
def search_documents(request: DocumentSearchRequest):
    return rag_service.search(request.query, top_k=request.top_k)