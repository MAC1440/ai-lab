from fastapi import APIRouter, HTTPException, Response, status

from dependencies import mcp_service
from services.agent_service import AgentService
from services.mcp_service import MCPServerInput


router = APIRouter(prefix="/mcp", tags=["MCP"])
agent_service = AgentService()


def _agent_ids() -> set[str]:
    return {agent["id"] for agent in agent_service.list_agents()}


@router.get("")
def get_mcp_settings():
    return mcp_service.snapshot()


@router.put("/servers/{server_id}")
def save_mcp_server(server_id: str, request: MCPServerInput):
    try:
        return mcp_service.save_server(
            server_id, request, valid_agent_ids=_agent_ids()
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.delete(
    "/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_mcp_server(server_id: str):
    try:
        mcp_service.delete_server(server_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/servers/{server_id}/tools")
async def discover_mcp_tools(server_id: str):
    try:
        return await mcp_service.discover_tools(server_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.post("/servers/{server_id}/test")
async def test_mcp_server(server_id: str):
    try:
        return await mcp_service.test_server(server_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
