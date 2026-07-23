from typing import Literal

from fastapi import APIRouter, HTTPException, Response, status

from dependencies import model_capability_service, provider_settings_service
from services.agent_service import AgentService
from services.model_capability_service import ModelCapabilityInput
from services.provider_settings_service import AgentModelInput, ProviderInput


router = APIRouter(prefix="/settings", tags=["Model settings"])
agent_service = AgentService()


def _agent_ids() -> list[str]:
    return [agent["id"] for agent in agent_service.list_agents()]


@router.get("/models")
def get_model_settings():
    return provider_settings_service.snapshot(_agent_ids())


@router.put("/providers/{provider_id}")
def save_provider(provider_id: str, request: ProviderInput):
    try:
        return provider_settings_service.save_provider(provider_id, request)
    except (ValueError, RuntimeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.delete(
    "/providers/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_provider(provider_id: str):
    try:
        provider_settings_service.delete_provider(provider_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/providers/{provider_id}/models")
def discover_models(provider_id: str):
    try:
        return provider_settings_service.discover_models(provider_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.post("/providers/{provider_id}/test")
def test_provider(provider_id: str):
    try:
        return provider_settings_service.test_provider(provider_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.put("/agents/{agent_id}")
def save_agent_model(agent_id: str, request: AgentModelInput):
    try:
        agent_service.get_agent(agent_id)
        return provider_settings_service.save_agent(agent_id, request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


TaskStage = Literal["planning", "generation", "repair"]


@router.put("/agents/{agent_id}/stages/{stage}")
def save_task_stage_model(
    agent_id: str,
    stage: TaskStage,
    request: AgentModelInput,
):
    try:
        agent_service.get_agent(agent_id)
        return provider_settings_service.save_task_stage(
            agent_id,
            stage,
            request,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.delete(
    "/agents/{agent_id}/stages/{stage}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_task_stage_model(agent_id: str, stage: TaskStage):
    try:
        provider_settings_service.delete_task_stage(agent_id, stage)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/model-capabilities")
def list_model_capabilities():
    return {"profiles": model_capability_service.list_profiles()}


@router.put("/model-capabilities")
def save_model_capability(request: ModelCapabilityInput):
    try:
        provider_settings_service.get_provider(request.provider_id)
        return model_capability_service.save_profile(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.delete(
    "/model-capabilities",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_model_capability(provider_id: str, model: str):
    try:
        model_capability_service.delete_profile(provider_id, model)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
