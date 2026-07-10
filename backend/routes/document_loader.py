from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.agent_service import AgentService
from services.document_loader import DocumentLoader
from services.rag import RAGService


class DocumentSearchRequest(BaseModel):
    query: str
    top_k: int = 3


class DocumentAskRequest(BaseModel):
    query: str
    top_k: int = 3
    stream: bool = False
    agent_id: str = "general"


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)

loader = DocumentLoader()
rag_service = RAGService()
agent_service = AgentService()


@router.get("/")
def list_documents():
    documents = loader.load_markdown_documents()

    return {
        "documents": documents,
    }


@router.post("/ask")
def ask_question(request: DocumentAskRequest):
    try:
        agent = agent_service.get_agent(request.agent_id)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    if request.stream:
        return StreamingResponse(
            rag_service.ask(
                query=request.query,
                top_k=request.top_k,
                stream=True,
                agent=agent,
            ),
            media_type="text/plain",
        )

    return rag_service.ask(
        query=request.query,
        top_k=request.top_k,
        stream=False,
        agent=agent,
    )

@router.post("/index")
def index_documents():
    documents = loader.load_markdown_documents()

    return rag_service.index_documents(documents)


@router.post("/search")
def search_documents(request: DocumentSearchRequest):
    return rag_service.search(
        query=request.query,
        top_k=request.top_k,
    )