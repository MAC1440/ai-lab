import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.embeddings import router as embeddings_router
from routes.document_loader import router as document_loader_router
from routes.chat import router as chat_router


def create_app() -> FastAPI:
    load_dotenv()

    app = FastAPI(
        title="AI Lab Backend",
        version="1.0.0",
        description="FastAPI service for chat, streaming, embeddings, and RAG workflows",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    app.include_router(chat_router)
    app.include_router(embeddings_router)
    app.include_router(document_loader_router)

    return app


app = create_app()