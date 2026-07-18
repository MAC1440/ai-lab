import os

from dotenv import load_dotenv

# Load configuration before importing routes and their dependencies.
load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from routes.agents import router as agents_router  # noqa: E402
from routes.changes import router as changes_router  # noqa: E402
from routes.repairs import router as repairs_router  # noqa: E402
from routes.scaffolds import router as scaffolds_router  # noqa: E402
from routes.verifications import router as verifications_router  # noqa: E402
from routes.workspaces import router as workspaces_router  # noqa: E402


def create_app() -> FastAPI:
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
    app.include_router(workspaces_router)
    app.include_router(changes_router)
    app.include_router(repairs_router)
    app.include_router(scaffolds_router)
    app.include_router(verifications_router)

    return app


app = create_app()
