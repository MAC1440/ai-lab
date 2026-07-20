import asyncio
import json
from typing import Any, Dict, Iterator, List, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from dependencies import (
    conversation_service,
    provider_settings_service,
    mcp_service,
    project_context_service,
    project_detection_service,
    run_cancellation_service,
)
from services.agent_runner import AgentRunner
from services.agent_service import AgentService
from services.conversation_service import ConversationStateError
from services.conversation_store import ConversationNotFoundError
from services.pydantic_runner import PydanticAgentRunner


router = APIRouter(
    prefix="/agent",
    tags=["Agent"],
)

agent_service = AgentService()
agent_runner = AgentRunner(agent_service=agent_service)

pydantic_runner = PydanticAgentRunner(
    agent_service=agent_service,
    project_context_service=project_context_service,
    provider_settings_service=provider_settings_service,
    mcp_service=mcp_service,
)


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
    tool_policy: Literal["auto", "inspect", "propose"] = "auto"
    repair_task_id: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    session_id: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    run_id: str = Field(default_factory=lambda: uuid4().hex, min_length=8, max_length=100)
    rag_enabled: Optional[bool] = None
    tools_enabled: Optional[bool] = None
    enabled_tools: Optional[List[str]] = None


@router.get("/list")
def list_agents():
    agents = agent_service.list_agents()
    for agent in agents:
        runtime = provider_settings_service.resolve_agent(
            agent["id"], fallback_model=agent["model"]
        )
        agent["model"] = runtime["model"]
        agent["provider_id"] = runtime["provider_id"]
    return {
        "agents": agents,
    }


@router.get("/recommendation")
def recommend_agent():
    try:
        overview = project_detection_service.inspect_workspace()
        recommendation = agent_service.recommend_agent(
            project["type"] for project in overview["projects"]
        )
        recommendation["projects"] = overview["projects"]
        return recommendation
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/chat/pydantic/stream")
async def pydantic_agent_chat_stream(
    request: AgentChatRequest,
):
    history = _serialize_history(request.history)

    async def generate_events():
        try:
            await run_cancellation_service.register(request.run_id)
            run_history = history
            if request.session_id:
                run_history = conversation_service.prepare_run(
                    session_id=request.session_id,
                    agent_id=request.agent_id,
                    prompt=request.prompt,
                    rag_top_k=request.rag_top_k,
                    rag_distance_threshold=request.rag_distance_threshold,
                )
            async for event in pydantic_runner.run_events(
                agent_id=request.agent_id,
                prompt=request.prompt,
                history=run_history,
                rag_top_k=request.rag_top_k,
                rag_distance_threshold=request.rag_distance_threshold,
                tool_policy=request.tool_policy,
                repair_task_id=request.repair_task_id,
                rag_enabled=request.rag_enabled,
                tools_enabled=request.tools_enabled,
                enabled_tools=request.enabled_tools,
            ):
                if event.get("type") == "done" and request.session_id:
                    event["result"]["session_id"] = request.session_id
                    conversation_service.complete_run(
                        session_id=request.session_id,
                        result=event["result"],
                    )
                yield _encode_ndjson(event)

        except asyncio.CancelledError:
            # Re-raising is what closes Pydantic AI's model context and the
            # underlying HTTP stream to Ollama immediately.
            raise

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
        except ConversationNotFoundError as error:
            yield _encode_ndjson(
                {
                    "type": "error",
                    "message": str(error),
                    "status_code": 404,
                }
            )
        except ConversationStateError as error:
            yield _encode_ndjson(
                {
                    "type": "error",
                    "message": str(error),
                    "status_code": 409,
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
            yield _encode_ndjson(
                {
                    "type": "error",
                    "message": str(error),
                    "status_code": 500,
                }
            )
        finally:
            await run_cancellation_service.unregister(request.run_id)

    return StreamingResponse(
        generate_events(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/runs/{run_id}/cancel")
async def cancel_agent_run(run_id: str):
    result = await run_cancellation_service.cancel(run_id)
    return {
        "run_id": result.run_id,
        "cancelled": result.cancelled,
    }


@router.post("/chat/stream")
def agent_chat_stream(request: AgentChatRequest):
    """Stream agent lifecycle events as newline-delimited JSON.

    Pydantic request validation still happens before streaming begins. Runtime
    failures happen after the response headers are sent, so they are returned
    as a final ``error`` event rather than as a new HTTP status code.
    """

    if request.tool_policy != "auto":
        raise HTTPException(
            status_code=400,
            detail=(
                "tool_policy is enforced only by "
                "/agent/chat/pydantic/stream"
            ),
        )

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
