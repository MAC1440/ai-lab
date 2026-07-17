from typing import Literal, Optional

from fastapi import APIRouter, HTTPException

from dependencies import change_service
from services.change_service import (
    ChangeProposalConflictError,
    ChangeProposalNotFoundError,
    ChangeProposalStateError,
)


ChangeProposalStatus = Literal["pending", "approved", "rejected"]

router = APIRouter(
    prefix="/changes",
    tags=["Changes"],
)


@router.get("")
def list_change_proposals(
    status: Optional[ChangeProposalStatus] = None,
    change_set_id: Optional[str] = None,
    repair_task_id: Optional[str] = None,
):
    try:
        return {
            "proposals": change_service.list_proposals(
                status=status,
                change_set_id=change_set_id,
                repair_task_id=repair_task_id,
            ),
        }
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/{proposal_id}")
def get_change_proposal(proposal_id: str):
    try:
        return change_service.get(proposal_id)
    except ChangeProposalNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/{proposal_id}/approve")
def approve_change_proposal(proposal_id: str):
    try:
        return change_service.approve(proposal_id)
    except ChangeProposalNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (
        ChangeProposalStateError,
        ChangeProposalConflictError,
    ) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except (ValueError, IsADirectoryError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/{proposal_id}/reject")
def reject_change_proposal(proposal_id: str):
    try:
        return change_service.reject(proposal_id)
    except ChangeProposalNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ChangeProposalStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/sets/{change_set_id}/approve")
def approve_change_set(change_set_id: str):
    try:
        return {"proposals": change_service.approve_change_set(change_set_id)}
    except ChangeProposalNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (ChangeProposalStateError, ChangeProposalConflictError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except (ValueError, IsADirectoryError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/sets/{change_set_id}/reject")
def reject_change_set(change_set_id: str):
    try:
        return {"proposals": change_service.reject_change_set(change_set_id)}
    except ChangeProposalNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ChangeProposalStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
