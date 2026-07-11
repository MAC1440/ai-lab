from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.agent_runner import AgentRunner


router = APIRouter(
    prefix="/agent",
    tags=["Agent"],
)

agent_runner = AgentRunner()


class AgentChatRequest(BaseModel):
    agent_id: str = "coding"
    prompt: str = Field(min_length=1)
    history: Optional[List[Dict[str, Any]]] = None


@router.post("/chat")
def agent_chat(request: AgentChatRequest):
    if not request.prompt.strip():
        raise HTTPException(
            status_code=400,
            detail="Prompt cannot be empty",
        )

    try:
        return agent_runner.run(
            agent_id=request.agent_id,
            prompt=request.prompt,
            history=request.history,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except PermissionError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error

    except RuntimeError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error