from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tools.file_tools import list_files, read_file


router = APIRouter(prefix="/tools", tags=["Tools"])


class ListFilesRequest(BaseModel):
    folder: str = "."


class ReadFileRequest(BaseModel):
    path: str


@router.post("/list-files")
def list_project_files(request: ListFilesRequest):
    try:
        return {
            "files": list_files(request.folder)
        }
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/read-file")
def read_project_file(request: ReadFileRequest):
    try:
        return read_file(request.path)
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))