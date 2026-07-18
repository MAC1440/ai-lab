from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from dependencies import repair_service
from services.repair_service import RepairTaskStateError
from services.repair_store import RepairTaskNotFoundError
from services.verification_store import VerificationRunNotFoundError


router = APIRouter(prefix="/repairs", tags=["Repairs"])


class CreateRepairTaskRequest(BaseModel):
    verification_run_id: str = Field(min_length=1, max_length=100)


@router.get("")
def list_repair_tasks(include_dismissed: bool = False, limit: int = 50):
    try:
        return {
            "tasks": repair_service.list_tasks(
                include_dismissed=include_dismissed,
                limit=limit,
            )
        }
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("")
def create_repair_task(request: CreateRepairTaskRequest):
    try:
        return repair_service.create_from_verification(
            request.verification_run_id
        )
    except VerificationRunNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RepairTaskStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/{task_id}")
def get_repair_task(task_id: str):
    try:
        return repair_service.get_task(task_id)
    except RepairTaskNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/{task_id}/dismiss")
def dismiss_repair_task(task_id: str):
    try:
        return repair_service.dismiss(task_id)
    except RepairTaskNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RepairTaskStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/{task_id}/reopen")
def reopen_repair_task(task_id: str):
    try:
        return repair_service.reopen(task_id)
    except RepairTaskNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RepairTaskStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/{task_id}/attempts")
def start_repair_attempt(task_id: str):
    try:
        return repair_service.start_agent_attempt(task_id)
    except RepairTaskNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RepairTaskStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
