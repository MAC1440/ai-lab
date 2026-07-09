import os
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from services.memory import ConversationMemory
from services.ollama_client import OllamaClient
from services.rag import RAGService
from services.embeddings import EmbeddingService


router = APIRouter(tags=["Chat"])

ollama_client = OllamaClient(
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    model=os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b"),
)

embedding_service = EmbeddingService(ollama_client)
rag_service = RAGService(embedding_service)
conversation_memory = ConversationMemory()


class ChatRequest(BaseModel):
    prompt: str
    stream: bool = False
    system_prompt: Optional[str] = None
    use_rag: bool = False
    documents: Optional[List[str]] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "prompt": "Explain RAG in one paragraph",
                "stream": False,
                "use_rag": True,
                "documents": ["RAG retrieves relevant context before answering."],
            }
        }
    )


class ChatResponse(BaseModel):
    answer: str
    used_rag: bool


@router.get("/models")
def list_models():
    return ollama_client.health()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    context = ""
    if request.use_rag and request.documents:
        context = rag_service.build_context(request.prompt, request.documents)

    system_prompt = request.system_prompt or "You are a helpful assistant."
    if context:
        system_prompt = f"{system_prompt}\n\nUse this context when relevant:\n{context}"

    conversation_memory.add_user_message(request.prompt)

    answer = ollama_client.chat(
        request.prompt,
        system_prompt=system_prompt,
        history=conversation_memory.get_recent_messages(),
    )

    conversation_memory.add_assistant_message(answer)

    return {"answer": answer, "used_rag": bool(context)}


@router.post("/chat/stream")
def stream_chat(request: ChatRequest):
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    def generate():
        context = ""
        if request.use_rag and request.documents:
            context = rag_service.build_context(request.prompt, request.documents)

        system_prompt = request.system_prompt or "You are a helpful assistant."
        if context:
            system_prompt = f"{system_prompt}\n\nUse this context when relevant:\n{context}"

        for chunk in ollama_client.stream_chat(
            request.prompt,
            system_prompt=system_prompt,
            history=conversation_memory.get_recent_messages(),
        ):
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain")