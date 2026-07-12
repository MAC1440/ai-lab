from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.agent_runner import AgentRunner

router = APIRouter(
    prefix="/agent",
    tags=["Agent"],
)

agent_runner = AgentRunner()


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class AgentChatRequest(BaseModel):
    agent_id: str = "coding"
    prompt: str = Field(min_length=1)
    history: Optional[List[HistoryMessage]] = None
    rag_top_k: int = Field(default=3, ge=1, le=10)
    rag_distance_threshold: Optional[float] = Field(
        default=1.0,
        ge=0.0,
    )


@router.post("/chat")
def agent_chat(request: AgentChatRequest):
    try:
        history = None
        if request.history:
            history = [
                message.model_dump()
                for message in request.history
            ]

        return agent_runner.run(
            agent_id=request.agent_id,
            prompt=request.prompt,
            history=history,
            rag_top_k=request.rag_top_k,
            rag_distance_threshold=request.rag_distance_threshold,
        )
    except PermissionError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except RuntimeError as error:
        # Ollama, embeddings, Chroma, model, tool-loop,
        # and other upstream failures.
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error
