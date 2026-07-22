from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from dependencies import (
    project_task_service,
    run_cancellation_service,
    verification_service,
)
from services.project_task_service import ProjectTaskStateError
from services.project_task_store import ProjectTaskNotFoundError
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
