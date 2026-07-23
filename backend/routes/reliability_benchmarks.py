import asyncio
import json
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from dependencies import reliability_benchmark_service
from services.reliability_benchmark_service import (
    ReliabilityBenchmarkBusyError,
)
from services.reliability_benchmark_store import (
    ReliabilityBenchmarkRunNotFoundError,
)
from services.task_model_client import TaskModelOutputError

router = APIRouter(
    prefix="/reliability-benchmarks",
    tags=["Reliability benchmarks"],
)


class RunReliabilityBenchmarkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suite: Literal["quick", "full"] = "quick"
    repetitions: int = Field(default=1, ge=1, le=3)
    agent_override: Literal[
        "assigned",
        "coding",
        "unity",
        "web",
    ] = "assigned"


@router.get("/scenarios")
def list_reliability_scenarios():
    return {"scenarios": reliability_benchmark_service.list_scenarios()}


@router.get("/runs")
def list_reliability_runs(limit: int = 20):
    try:
        return {"runs": reliability_benchmark_service.list_runs(limit=limit)}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/runs/{run_id}")
def get_reliability_run(run_id: str):
    try:
        return reliability_benchmark_service.get_run(run_id)
    except ReliabilityBenchmarkRunNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post(
    "/run/stream",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Newline-delimited reliability benchmark events.",
            "content": {
                "application/x-ndjson": {"schema": {"type": "string"}}
            },
        }
    },
)
async def run_reliability_benchmark_stream(
    request: RunReliabilityBenchmarkRequest,
):
    async def generate_events():
        try:
            async for event in reliability_benchmark_service.run_events(
                suite=request.suite,
                repetitions=request.repetitions,
                agent_override=request.agent_override,
            ):
                yield _encode_ndjson(event)
        except asyncio.CancelledError:
            raise
        except ReliabilityBenchmarkBusyError as error:
            yield _encode_ndjson(
                {"type": "error", "status_code": 409, "message": str(error)}
            )
        except TaskModelOutputError as error:
            yield _encode_ndjson(
                {
                    "type": "error",
                    "status_code": 422,
                    "code": "structured_output_failed",
                    "stage": error.stage,
                    "model": error.model,
                    "message": str(error),
                }
            )
        except (OSError, UnicodeError, ValueError, RuntimeError) as error:
            yield _encode_ndjson(
                {"type": "error", "status_code": 400, "message": str(error)}
            )
        except Exception as error:  # noqa: BLE001  # pragma: no cover
            yield _encode_ndjson(
                {"type": "error", "status_code": 500, "message": str(error)}
            )

    return StreamingResponse(
        generate_events(),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


def _encode_ndjson(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"
