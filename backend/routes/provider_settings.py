from fastapi import APIRouter, HTTPException, Response, status

from dependencies import provider_settings_service
from services.agent_service import AgentService
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
