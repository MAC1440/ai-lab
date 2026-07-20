import json
from typing import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from dependencies import unity_docs_service


router = APIRouter(prefix="/knowledge/unity", tags=["Unity knowledge"])


class PreviewRequest(BaseModel):
    source_directory: str = Field(min_length=1, max_length=1000)
    relative_file: str = Field(min_length=1, max_length=1000)


class IndexRequest(BaseModel):
    source_directory: str = Field(min_length=1, max_length=1000)
    batch_size: int = Field(default=24, ge=1, le=100)


@router.get("/status")
def status():
    return unity_docs_service.status()


@router.post("/preview")
def preview(request: PreviewRequest):
    try:
        return unity_docs_service.preview(
            request.source_directory,
            request.relative_file,
        )
    except (OSError, UnicodeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/index/stream")
def index_stream(request: IndexRequest):
    def events() -> Iterator[str]:
        try:
            for event in unity_docs_service.index_stream(
                request.source_directory,
                batch_size=request.batch_size,
            ):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as error:
            yield json.dumps(
                {"type": "error", "message": str(error)},
                ensure_ascii=False,
            ) + "\n"

    return StreamingResponse(events(), media_type="application/x-ndjson")
