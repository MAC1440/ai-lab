from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.agent_service import AgentService
from tools.file_tools import list_files, read_file, write_file


router = APIRouter(
    prefix="/tools",
    tags=["Tools"],
)

agent_service = AgentService()


class ListFilesRequest(BaseModel):
    agent_id: str = "coding"
    folder: str = "."


class ReadFileRequest(BaseModel):
    agent_id: str = "coding"
    path: str


class WriteFileRequest(BaseModel):
    agent_id: str = "coding"
    path: str
    content: str
    overwrite: bool = False


@router.post("/list-files")
def list_project_files(request: ListFilesRequest):
    try:
        agent_service.ensure_tool_allowed(
            agent_id=request.agent_id,
            tool_name="list_files",
        )

        files = list_files(request.folder)

        return {
            "folder": request.folder,
            "files": files,
        }

    except PermissionError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error

    except (
        FileNotFoundError,
        NotADirectoryError,
        RuntimeError,
    ) as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


@router.post("/read-file")
def read_project_file(request: ReadFileRequest):
    try:
        agent_service.ensure_tool_allowed(
            agent_id=request.agent_id,
            tool_name="read_file",
        )

        return read_file(request.path)

    except PermissionError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error

    except (
        FileNotFoundError,
        IsADirectoryError,
        RuntimeError,
        ValueError,
    ) as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


@router.post("/write-file")
def write_project_file(request: WriteFileRequest):
    try:
        agent_service.ensure_tool_allowed(
            agent_id=request.agent_id,
            tool_name="write_file",
        )

        return write_file(
            file_path=request.path,
            content=request.content,
            overwrite=request.overwrite,
        )

    except PermissionError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        ) from error

    except (
        FileExistsError,
        IsADirectoryError,
        RuntimeError,
        ValueError,
    ) as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error