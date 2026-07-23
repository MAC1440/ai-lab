import json
from typing import Any, Dict, Literal

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from dependencies import model_benchmark_service, model_capability_service
from services.task_model_client import TaskModelOutputError


router = APIRouter(prefix="/model-benchmarks", tags=["Model benchmarks"])


class RunModelBenchmarkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: Literal["coding", "unity", "web"] = "coding"


@router.get("/recommendations")
def get_model_assignment_recommendations():
    return model_capability_service.recommend_assignments()


@router.post(
    "/run/stream",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Newline-delimited benchmark events.",
            "content": {
                "application/x-ndjson": {"schema": {"type": "string"}}
            },
        }
    },
)
async def run_model_benchmark_stream(request: RunModelBenchmarkRequest):
    async def generate_events():
        try:
            async for event in model_benchmark_service.run_events(
                agent_id=request.agent_id
            ):
                yield _encode_ndjson(event)
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
        except (OSError, ValueError, RuntimeError) as error:
            yield _encode_ndjson(
                {"type": "error", "status_code": 400, "message": str(error)}
            )
        except Exception as error:  # pragma: no cover - provider boundary
            yield _encode_ndjson(
                {"type": "error", "status_code": 500, "message": str(error)}
            )

    return StreamingResponse(
        generate_events(),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


def _encode_ndjson(event: Dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False) + "\n"
