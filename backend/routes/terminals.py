from __future__ import annotations

import asyncio
import ipaddress
import os
from typing import Literal, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, Field

from dependencies import workspace_service
from services.terminal_service import (
    DEFAULT_COLUMNS,
    DEFAULT_ROWS,
    MAX_COLUMNS,
    MAX_ROWS,
    MIN_COLUMNS,
    MIN_ROWS,
    TerminalService,
    TerminalSessionClosedError,
    TerminalSessionNotFoundError,
    TerminalUnavailableError,
)


router = APIRouter(prefix="/terminals", tags=["Terminals"])

terminal_service = TerminalService(
    workspace_service,
    max_history_characters=int(
        os.getenv("TERMINAL_MAX_HISTORY_CHARS", "200000")
    ),
    max_sessions=int(os.getenv("TERMINAL_MAX_SESSIONS", "4")),
)


class CreateTerminalSessionRequest(BaseModel):
    shell: Literal["auto", "pwsh", "powershell"] = "auto"
    columns: int = Field(DEFAULT_COLUMNS, ge=MIN_COLUMNS, le=MAX_COLUMNS)
    rows: int = Field(DEFAULT_ROWS, ge=MIN_ROWS, le=MAX_ROWS)


class LaunchClaudeRequest(BaseModel):
    mode: Literal["new", "continue", "resume"] = "new"
    resume_id: Optional[str] = None


def _remote_terminal_enabled() -> bool:
    return os.getenv("TERMINAL_ALLOW_REMOTE", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _host_is_loopback(host: str) -> bool:
    clean_host = host.strip().lower()
    if clean_host == "localhost":
        return True

    try:
        return ipaddress.ip_address(clean_host).is_loopback
    except ValueError:
        return False


def require_loopback_terminal_client(request: Request) -> None:
    """Block terminal HTTP controls from non-loopback clients by default."""
    if _remote_terminal_enabled():
        return

    client = request.client
    if client is not None and _host_is_loopback(client.host):
        return

    raise HTTPException(
        status_code=403,
        detail="Terminal access is loopback-only",
    )


# REST controls can start processes or send commands, so they receive the same
# loopback boundary as the terminal WebSocket. This remains opt-out through the
# existing TERMINAL_ALLOW_REMOTE setting for deliberate LAN deployments.
http_router = APIRouter(
    dependencies=[Depends(require_loopback_terminal_client)],
)


@http_router.get("/diagnostics")
def get_terminal_diagnostics():
    return terminal_service.diagnostics()


@http_router.get("/sessions")
def list_terminal_sessions():
    return terminal_service.list_sessions()


@http_router.post("/sessions")
async def create_terminal_session(request: CreateTerminalSessionRequest):
    try:
        return await terminal_service.create_session(
            shell=request.shell,
            columns=request.columns,
            rows=request.rows,
        )
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (ValueError, TypeError, TerminalUnavailableError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@http_router.get("/sessions/{session_id}")
def get_terminal_session(session_id: str):
    try:
        return terminal_service.get_session(session_id)
    except TerminalSessionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@http_router.post("/sessions/{session_id}/claude")
async def launch_claude(
    session_id: str,
    request: LaunchClaudeRequest,
):
    try:
        return await terminal_service.launch_claude(
            session_id,
            mode=request.mode,
            resume_id=request.resume_id,
        )
    except TerminalSessionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except TerminalSessionClosedError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except (TerminalUnavailableError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@http_router.post("/sessions/{session_id}/claude/install")
async def install_claude(session_id: str):
    try:
        return await terminal_service.install_claude(session_id)
    except TerminalSessionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except TerminalSessionClosedError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except TerminalUnavailableError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@http_router.post("/sessions/{session_id}/interrupt")
async def interrupt_terminal_session(session_id: str):
    try:
        return await terminal_service.interrupt(session_id)
    except TerminalSessionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except TerminalSessionClosedError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@http_router.delete("/sessions/{session_id}")
async def close_terminal_session(session_id: str):
    try:
        return await terminal_service.close_session(session_id)
    except TerminalSessionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.websocket("/sessions/{session_id}/ws")
async def terminal_websocket(websocket: WebSocket, session_id: str):
    if not _websocket_client_allowed(websocket):
        await websocket.close(
            code=4403,
            reason="Terminal access is loopback-only",
        )
        return

    try:
        queue, snapshot = terminal_service.subscribe(session_id)
    except TerminalSessionNotFoundError:
        await websocket.close(code=4404, reason="Terminal session not found")
        return

    await websocket.accept()
    await websocket.send_json(
        {
            "type": "snapshot",
            **snapshot,
        }
    )
    sender = asyncio.create_task(_send_terminal_events(websocket, queue))

    try:
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")

            try:
                if message_type == "input":
                    await terminal_service.write(
                        session_id,
                        str(message.get("data", "")),
                    )
                elif message_type == "resize":
                    await terminal_service.resize(
                        session_id,
                        columns=message.get("columns"),
                        rows=message.get("rows"),
                    )
                elif message_type == "ping":
                    await websocket.send_json({"type": "pong"})
                else:
                    raise ValueError(
                        f"Unsupported terminal message: {message_type}"
                    )
            except (
                TerminalSessionNotFoundError,
                TerminalSessionClosedError,
                TypeError,
                ValueError,
            ) as error:
                await websocket.send_json(
                    {
                        "type": "error",
                        "error": str(error),
                    }
                )
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        await asyncio.gather(sender, return_exceptions=True)
        terminal_service.unsubscribe(session_id, queue)


async def _send_terminal_events(
    websocket: WebSocket,
    queue: asyncio.Queue[dict],
) -> None:
    while True:
        event = await queue.get()
        await websocket.send_json(event)


def _websocket_client_allowed(websocket: WebSocket) -> bool:
    if _remote_terminal_enabled():
        return True

    client = websocket.client
    return client is not None and _host_is_loopback(client.host)


router.include_router(http_router)
