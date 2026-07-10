from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dependencies import workspace_service


router = APIRouter(
    prefix="/workspaces",
    tags=["Workspaces"],
)


class BrowseDirectoryRequest(BaseModel):
    path: str


class SelectWorkspaceRequest(BaseModel):
    path: str


@router.get("/drives")
def list_drives():
    return {
        "drives": workspace_service.list_drives(),
    }


@router.post("/browse")
def browse_directory(request: BrowseDirectoryRequest):
    try:
        return {
            "path": request.path,
            "items": workspace_service.list_directory(request.path),
        }
    except (
        FileNotFoundError,
        NotADirectoryError,
        PermissionError,
        OSError,
    ) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/select")
def select_workspace(request: SelectWorkspaceRequest):
    try:
        return workspace_service.set_workspace(request.path)
    except (
        FileNotFoundError,
        NotADirectoryError,
        PermissionError,
    ) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/active")
def get_active_workspace():
    return workspace_service.get_workspace_info()