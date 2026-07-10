from fastapi import APIRouter, HTTPException

from services.agent_service import AgentService


router = APIRouter(
    prefix="/agents",
    tags=["Agents"],
)

agent_service = AgentService()


@router.get("/")
def list_agents():
    return {
        "agents": agent_service.list_agents(),
    }


@router.get("/{agent_id}")
def get_agent(agent_id: str):
    try:
        return agent_service.get_agent(agent_id)
    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error