import sqlite3

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from dependencies import project_index_service

router = APIRouter(prefix="/project-index", tags=["Project index"])


class RefreshProjectIndexRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rebuild: bool = False


class QueryProjectIndexRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=12_000)
    limit: int = Field(default=8, ge=1, le=50)
    project_root: str | None = Field(default=None, max_length=500)
    refresh: bool = True


@router.get("/status")
def get_project_index_status():
    try:
        return project_index_service.status()
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except sqlite3.Error as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/refresh")
def refresh_project_index(request: RefreshProjectIndexRequest):
    try:
        return project_index_service.refresh(rebuild=request.rebuild)
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except sqlite3.Error as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (OSError, UnicodeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/query")
def query_project_index(request: QueryProjectIndexRequest):
    try:
        return project_index_service.query(
            request.query,
            limit=request.limit,
            project_root=request.project_root,
            refresh=request.refresh,
        )
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except sqlite3.Error as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (OSError, UnicodeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
