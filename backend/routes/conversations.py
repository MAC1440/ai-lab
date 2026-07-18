from typing import Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from dependencies import conversation_service
from services.conversation_service import ConversationStateError
from services.conversation_store import ConversationNotFoundError


router = APIRouter(prefix="/conversations", tags=["Conversations"])


class CreateConversationRequest(BaseModel):
    agent_id: str = Field(min_length=1, max_length=50)
    title: str = Field(default="New conversation", min_length=1, max_length=100)
    rag_top_k: int = Field(default=3, ge=1, le=10)
    rag_distance_threshold: Optional[float] = Field(default=1.0, ge=0)


class UpdateConversationRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=100)
    status: Optional[str] = None


@router.get("")
def list_conversations(include_archived: bool = False):
    try:
        return {"sessions": conversation_service.list_sessions(include_archived=include_archived)}
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("")
def create_conversation(request: CreateConversationRequest):
    try:
        return conversation_service.create_session(**request.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/{session_id}")
def get_conversation(session_id: str):
    try:
        return conversation_service.get_session(session_id)
    except ConversationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.patch("/{session_id}")
def update_conversation(session_id: str, request: UpdateConversationRequest):
    try:
        return conversation_service.update_session(session_id, **request.model_dump())
    except ConversationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (ValueError, ConversationStateError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.delete("/{session_id}", status_code=204)
def delete_conversation(session_id: str):
    try:
        conversation_service.delete_session(session_id)
        return Response(status_code=204)
    except ConversationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
