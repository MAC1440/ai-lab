from fastapi import APIRouter, HTTPException

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
def metrics():
    return runtime_metrics_service.snapshot()
