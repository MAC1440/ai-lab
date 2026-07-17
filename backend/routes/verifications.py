import json
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from dependencies import (
    project_detection_service,
    repair_service,
    verification_service,
    verification_store,
    workspace_service,
)
from services.verification_service import (
    VerificationBusyError,
    VerificationRunNotActiveError,
    VerificationUnavailableError,
)
from services.verification_store import VerificationRunNotFoundError


router = APIRouter(
    prefix="/verifications",
    tags=["Verifications"],
)


class VerificationRunRequest(BaseModel):
    profile_id: str = Field(min_length=1, max_length=200)
    proposal_id: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    repair_task_id: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
    )


@router.get("/profiles")
def get_verification_profiles():
    try:
        return project_detection_service.inspect_workspace()
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/runs")
def list_verification_runs(limit: int = 20):
    try:
        workspace = str(workspace_service.get_workspace().resolve())
        return {
            "runs": verification_store.list_runs(
                workspace=workspace,
                limit=limit,
            )
        }
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/runs/{run_id}")
def get_verification_run(run_id: str):
    try:
        workspace = str(workspace_service.get_workspace().resolve())
        result = verification_store.get_run(run_id)

        if result["workspace"] != workspace:
            raise VerificationRunNotFoundError(f"Verification run not found: {run_id}")

        return result
    except VerificationRunNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/runs/{run_id}/cancel")
def cancel_verification_run(run_id: str):
    try:
        return verification_service.cancel(run_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except VerificationRunNotActiveError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/run/stream")
async def stream_verification_run(request: VerificationRunRequest):
    async def generate_events() -> AsyncIterator[str]:
        try:
            async for event in verification_service.run_events(
                profile_id=request.profile_id,
                proposal_id=request.proposal_id,
            ):
                if (
                    request.repair_task_id
                    and event.get("type") == "verification_done"
                ):
                    repair_service.record_verification(
                        request.repair_task_id,
                        event["result"],
                    )
                yield _encode_ndjson(event)
        except PermissionError as error:
            yield _error_event(str(error), 403)
        except ValueError as error:
            yield _error_event(str(error), 400)
        except LookupError as error:
            yield _error_event(str(error), 404)
        except (VerificationBusyError, VerificationUnavailableError) as error:
            yield _error_event(str(error), 409)
        except (FileNotFoundError, NotADirectoryError, RuntimeError) as error:
            yield _error_event(str(error), 409)
        except Exception as error:
            yield _error_event(
                f"Unexpected verification error: {error}",
                500,
            )

    return StreamingResponse(
        generate_events(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


def _error_event(message: str, status_code: int) -> str:
    return _encode_ndjson(
        {
            "type": "error",
            "message": message,
            "status_code": status_code,
        }
    )


def _encode_ndjson(event: Dict[str, Any]) -> str:
    return (
        json.dumps(
            event,
            ensure_ascii=False,
            default=str,
        )
        + "\n"
    )
