from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from dependencies import scaffold_service
from services.scaffold_service import (
    ScaffoldGenerationError,
    ScaffoldUnavailableError,
)


router = APIRouter(prefix="/scaffolds", tags=["Scaffolds"])


class CreateScaffoldRequest(BaseModel):
    scaffold_id: str = Field(min_length=1, max_length=50)
    target_directory: str = Field(min_length=1, max_length=240)
    project_name: str = Field(min_length=2, max_length=50)


@router.get("")
def list_scaffolds():
    return {"scaffolds": scaffold_service.list_scaffolds()}


@router.post("")
def create_scaffold(request: CreateScaffoldRequest):
    try:
        return scaffold_service.create_proposals(
            scaffold_id=request.scaffold_id,
            target_directory=request.target_directory,
            project_name=request.project_name,
        )
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except (ValueError, FileExistsError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except ScaffoldUnavailableError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ScaffoldGenerationError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
