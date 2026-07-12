from fastapi import APIRouter, HTTPException

from dependencies import change_service
from services.change_service import (
    ChangeProposalConflictError,
    ChangeProposalNotFoundError,
    ChangeProposalStateError,
)

router = APIRouter(
    prefix="/changes",
    tags=["Changes"],
)


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
    except (ChangeProposalStateError, ChangeProposalConflictError) as error:
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
