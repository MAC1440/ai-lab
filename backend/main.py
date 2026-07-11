import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.agents import router as agents_router
from routes.chat import router as chat_router
from routes.document_loader import router as documents_router
from routes.embeddings import router as embeddings_router
from routes.tools import router as tools_router
from routes.workspaces import router as workspaces_router
from routes.agent_chat import router as agent_chat_router

def create_app() -> FastAPI:
    load_dotenv()

    app = FastAPI(
        title="AI Lab Backend",
        version="1.0.0",
        description="Local AI assistant backend",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000",
        ).split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    app.include_router(agents_router)
    app.include_router(chat_router)
    app.include_router(documents_router)
    app.include_router(embeddings_router)
    app.include_router(workspaces_router)
    app.include_router(tools_router)
    app.include_router(agent_chat_router)

    return app


app = create_app()