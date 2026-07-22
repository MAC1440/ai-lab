import asyncio
import json
from typing import Any, Dict, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from dependencies import (
    project_task_service,
    project_task_orchestrator,
    run_cancellation_service,
    verification_service,
)
from services.project_task_service import ProjectTaskStateError
from services.project_task_store import ProjectTaskNotFoundError
from services.task_model_client import TaskModelOutputError
from services.verification_service import VerificationRunNotActiveError


router = APIRouter(prefix="/project-tasks", tags=["Project tasks"])


class CreateProjectTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    goal: str = Field(min_length=1, max_length=12_000)
    agent_id: Literal["coding", "unity", "web"] = "coding"
    verification_profile_id: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    max_attempts: int = Field(default=3, ge=1, le=5)


class SaveProjectTaskPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: Dict[str, Any]


class RunProjectTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(
        default_factory=lambda: uuid4().hex,
        min_length=8,
        max_length=100,
    )


@router.get("")
def list_project_tasks(limit: int = 50):
    try:
        return {"tasks": project_task_service.list_tasks(limit=limit)}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("")
def create_project_task(request: CreateProjectTaskRequest):
    try:
        return project_task_service.create(
            title=request.title,
            goal=request.goal,
            agent_id=request.agent_id,
            verification_profile_id=request.verification_profile_id,
            max_attempts=request.max_attempts,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/{task_id}")
def get_project_task(task_id: str):
    try:
        return project_task_service.get_task(task_id)
    except ProjectTaskNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/{task_id}/resume")
def resume_project_task(task_id: str):
    try:
        return project_task_service.resume(task_id)
    except ProjectTaskNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ProjectTaskStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.put("/{task_id}/plan")
def save_project_task_plan(task_id: str, request: SaveProjectTaskPlanRequest):
    try:
        return project_task_service.save_plan(task_id, request.plan)
    except ProjectTaskNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ProjectTaskStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/{task_id}/context")
def compile_project_task_context(task_id: str):
    try:
        return project_task_service.compile_context(task_id)
    except ProjectTaskNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ProjectTaskStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (OSError, UnicodeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post(
    "/{task_id}/run/stream",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Newline-delimited project-task events.",
            "content": {
                "application/x-ndjson": {
                    "schema": {"type": "string"},
                    "example": (
                        '{"type":"status","stage":"planning"}\n'
                        '{"type":"plan","plan":{}}\n'
                    ),
                }
            },
        }
    },
)
async def run_project_task_stream(
    task_id: str,
    request: RunProjectTaskRequest,
):
    async def generate_events():
        try:
            await run_cancellation_service.register(request.run_id)
            async for event in project_task_orchestrator.run_events(
                task_id=task_id,
                run_id=request.run_id,
            ):
                yield _encode_ndjson(event)
        except asyncio.CancelledError:
            raise
        except ProjectTaskNotFoundError as error:
            yield _encode_ndjson(
                {"type": "error", "status_code": 404, "message": str(error)}
            )
        except ProjectTaskStateError as error:
            yield _encode_ndjson(
                {"type": "error", "status_code": 409, "message": str(error)}
            )
        except TaskModelOutputError as error:
            yield _encode_ndjson(
                {
                    "type": "error",
                    "status_code": 422,
                    "code": "structured_output_failed",
                    "stage": error.stage,
                    "model": error.model,
                    "message": str(error),
                }
            )
        except (OSError, UnicodeError, ValueError, RuntimeError) as error:
            yield _encode_ndjson(
                {"type": "error", "status_code": 400, "message": str(error)}
            )
        except Exception as error:  # pragma: no cover - provider boundary
            yield _encode_ndjson(
                {"type": "error", "status_code": 500, "message": str(error)}
            )
        finally:
            await run_cancellation_service.unregister(request.run_id)

    return StreamingResponse(
        generate_events(),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@router.post("/{task_id}/cancel")
async def cancel_project_task(task_id: str):
    try:
        task = project_task_service.get_task(task_id)
        agent_run_id = task.get("current_agent_run_id")
        verification_run_id = (
            task.get("latest_verification_run_id")
            if task.get("status") == "verifying"
            else None
        )
        if agent_run_id:
            await run_cancellation_service.cancel(agent_run_id)
        if verification_run_id:
            try:
                verification_service.cancel(verification_run_id)
            except VerificationRunNotActiveError:
                pass
        return project_task_service.cancel(task_id)
    except ProjectTaskNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ProjectTaskStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def _encode_ndjson(event: Dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"
