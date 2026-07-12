import json
from typing import Any, Dict, Iterator, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.agent_runner import AgentRunner
from services.agent_service import AgentService

router = APIRouter(
    prefix="/agent",
    tags=["Agent"],
)

agent_service = AgentService()
agent_runner = AgentRunner(agent_service=agent_service)


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


@router.get("/list")
def list_agents():
    return {
        "agents": agent_service.list_agents(),
    }


@router.post("/chat")
def agent_chat(request: AgentChatRequest):
    """Existing non-streaming endpoint.

    It now consumes the same AgentRunner event loop used by /chat/stream.
    """

    try:
        return agent_runner.run(
            agent_id=request.agent_id,
            prompt=request.prompt,
            history=_serialize_history(request.history),
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
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error


@router.post("/chat/stream")
def agent_chat_stream(request: AgentChatRequest):
    """Stream agent lifecycle events as newline-delimited JSON.

    Pydantic request validation still happens before streaming begins. Runtime
    failures happen after the response headers are sent, so they are returned
    as a final ``error`` event rather than as a new HTTP status code.
    """

    history = _serialize_history(request.history)

    def generate_events() -> Iterator[str]:
        try:
            for event in agent_runner.run_events(
                agent_id=request.agent_id,
                prompt=request.prompt,
                history=history,
                rag_top_k=request.rag_top_k,
                rag_distance_threshold=request.rag_distance_threshold,
            ):
                yield _encode_ndjson(event)
        except PermissionError as error:
            yield _encode_ndjson(
                {
                    "type": "error",
                    "message": str(error),
                    "status_code": 403,
                }
            )
        except ValueError as error:
            yield _encode_ndjson(
                {
                    "type": "error",
                    "message": str(error),
                    "status_code": 400,
                }
            )
        except RuntimeError as error:
            yield _encode_ndjson(
                {
                    "type": "error",
                    "message": str(error),
                    "status_code": 502,
                }
            )
        except Exception as error:
            # Do not expose a Python traceback to the browser, but do send a
            # useful terminal event so the frontend can stop its loading UI.
            yield _encode_ndjson(
                {
                    "type": "error",
                    "message": f"Unexpected agent error: {error}",
                    "status_code": 500,
                }
            )

    return StreamingResponse(
        generate_events(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


def _serialize_history(
    history: Optional[List[HistoryMessage]],
) -> Optional[List[Dict[str, str]]]:
    if not history:
        return None

    return [
        message.model_dump()
        for message in history
    ]


def _encode_ndjson(event: Dict[str, Any]) -> str:
    return json.dumps(
        event,
        ensure_ascii=False,
        default=str,
    ) + "\n"