from typing import Any, Callable, Dict

from services.agent_service import AgentService
from tools.file_tools import list_files, read_file


ToolFunction = Callable[..., Any]


class ToolExecutor:
    def __init__(
        self,
        agent_service: AgentService | None = None,
    ):
        self.agent_service = agent_service or AgentService()

        self._tools: Dict[str, ToolFunction] = {
            "list_files": list_files,
            "read_file": read_file,
        }

    def execute(
        self,
        *,
        agent_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Any:
        self.agent_service.ensure_tool_allowed(
            agent_id=agent_id,
            tool_name=tool_name,
        )

        tool = self._tools.get(tool_name)

        if tool is None:
            raise ValueError(
                f"Unknown or unavailable tool: {tool_name}"
            )

        try:
            return tool(**arguments)
        except TypeError as error:
            raise ValueError(
                f"Invalid arguments for tool '{tool_name}': {arguments}"
            ) from error