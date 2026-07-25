import json
from typing import Iterator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from dependencies import knowledge_source_service


router = APIRouter(prefix="/knowledge/sources", tags=["Knowledge sources"])


class SelectionPreviewRequest(BaseModel):
    selections: list[str] = Field(min_length=1, max_length=200)


class IndexSourceRequest(BaseModel):
    source_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    selections: list[str] = Field(min_length=1, max_length=200)
    batch_size: int = Field(default=24, ge=1, le=100)


@router.get("")
def status():
    return knowledge_source_service.status()


@router.get("/browse")
def browse(path: str | None = Query(default=None, max_length=2000)):
    try:
        return knowledge_source_service.browse(path)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/preview")
def preview(request: SelectionPreviewRequest):
    try:
        return knowledge_source_service.preview(request.selections)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.delete("/{source_id}")
def remove(source_id: str):
    try:
        return knowledge_source_service.remove(source_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/index/stream")
def index_stream(request: IndexSourceRequest):
    def events() -> Iterator[str]:
        try:
            for event in knowledge_source_service.index_stream(
                **request.model_dump()
            ):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as error:
            yield json.dumps(
                {"type": "error", "message": str(error)},
                ensure_ascii=False,
            ) + "\n"

    return StreamingResponse(events(), media_type="application/x-ndjson")
