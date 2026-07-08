import os
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from services.embeddings import EmbeddingService
from services.memory import ConversationMemory
from services.ollama_client import OllamaClient
from services.rag import RAGService
from routes.embeddings import router as embeddings_router
from routes.document_loader import router as document_loader_router

def create_app() -> FastAPI:
    load_dotenv()

    app = FastAPI(
        title="AI Lab Backend",
        version="1.0.0",
        description="FastAPI service for chat, streaming, embeddings, and RAG workflows",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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

        class ConfigDict:
            json_schema_extra = {
                "example": {
                    "prompt": "Explain RAG in one paragraph",
                    "stream": False,
                    "use_rag": True,
                    "documents": ["RAG retrieves relevant context before answering."]
                }
            }

    class ChatResponse(BaseModel):
        answer: str
        used_rag: bool

        class ConfigDict:
            json_schema_extra = {
                "example": {
                    "answer": "RAG augments the model by retrieving relevant context before answering.",
                    "used_rag": True,
                }
            }

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    @app.get("/models")
    def list_models():
        return ollama_client.health()

    @app.post(
        "/chat",
        response_model=ChatResponse,
        summary="Generate a chat response",
        description="Send a prompt to the local Ollama-backed LLM. Can optionally use RAG context.",
    )
    def chat(request: ChatRequest):
        if not request.prompt.strip():
            raise HTTPException(status_code=400, detail="Prompt cannot be empty")

        if request.stream:
            return stream_chat(request)

        context = ""
        if request.use_rag and request.documents:
            context = rag_service.build_context(request.prompt, request.documents)

        system_prompt = request.system_prompt or "You are a helpful assistant."
        if context:
            system_prompt = f"{system_prompt}\n\nUse the following context when relevant:\n{context}"

        conversation_memory.add_user_message(request.prompt)
        answer = ollama_client.chat(
            request.prompt,
            stream=False,
            system_prompt=system_prompt,
            history=conversation_memory.get_recent_messages(),
        )
        conversation_memory.add_assistant_message(answer)
        return {"answer": answer, "used_rag": bool(context)}

    @app.post(
        "/chat/stream",
        summary="Stream a chat response",
        description="Streams the LLM response token by token over plain text.",
    )
    def stream_chat(request: ChatRequest):
        if not request.prompt.strip():
            raise HTTPException(status_code=400, detail="Prompt cannot be empty")

        def generate():
            context = ""
            if request.use_rag and request.documents:
                context = rag_service.build_context(request.prompt, request.documents)

            system_prompt = request.system_prompt or "You are a helpful assistant."
            if context:
                system_prompt = f"{system_prompt}\n\nUse the following context when relevant:\n{context}"

            for chunk in ollama_client.chat(
                request.prompt,
                stream=True,
                system_prompt=system_prompt,
                history=conversation_memory.get_recent_messages(),
            ):
                yield chunk

        return StreamingResponse(generate(), media_type="text/plain")

    @app.post(
        "/embed",
        summary="Create an embedding",
        description="Generates an embedding for a single text input using the configured embedding model.",
    )
    def embed_text(payload: dict):
        text = payload.get("text", "")
        if not text:
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        return {"embedding": embedding_service.embed_text(text)}

    @app.post(
        "/rag",
        summary="Build RAG context",
        description="Ranks provided documents against the query and returns the most relevant context.",
    )
    def rag_query(payload: dict):
        query = payload.get("query", "")
        documents = payload.get("documents", [])
        if not query:
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        return {"context": rag_service.build_context(query, documents)}

    return app


app = create_app()
app.include_router(embeddings_router)
app.include_router(document_loader_router)