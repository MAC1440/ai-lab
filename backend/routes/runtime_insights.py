from fastapi import APIRouter, HTTPException, Query

from dependencies import (
    hardware_profile_service,
    runtime_metrics_service,
    runtime_settings_service,
)
from services.runtime_settings_service import RuntimeSettingsDocument


router = APIRouter(prefix="/runtime", tags=["Runtime"])


@router.get("/hardware")
def hardware():
    return hardware_profile_service.snapshot()


@router.get("/settings")
def get_settings():
    return runtime_settings_service.get()


@router.put("/settings")
def save_settings(request: RuntimeSettingsDocument):
    try:
        return runtime_settings_service.save(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/settings/auto")
def auto_settings():
    hardware_result = hardware_profile_service.snapshot()
    context = hardware_result["recommendation"]["recommended_context_window"]
    return runtime_settings_service.apply_recommendation(context)


@router.get("/metrics")
def metrics(
    limit: int = Query(default=100, ge=1, le=100),
    stage: str | None = Query(default=None, min_length=1, max_length=40),
    agent_id: str | None = Query(default=None, min_length=1, max_length=100),
    model: str | None = Query(default=None, min_length=1, max_length=200),
):
    return runtime_metrics_service.snapshot(
        limit=limit,
        stage=stage,
        agent_id=agent_id,
        model=model,
    )


@router.delete("/metrics")
def clear_metrics():
    removed = runtime_metrics_service.clear()
    return {
        "removed": removed,
        "message": "Runtime metric history cleared.",
    }
