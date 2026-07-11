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

        # Only read-only tools are model-callable at this stage.
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
                f"Tool '{tool_name}' is not available to the agent runner"
            )

        normalized_arguments = self._validate_arguments(
            tool_name=tool_name,
            arguments=arguments,
        )

        try:
            return tool(**normalized_arguments)

        except TypeError as error:
            raise ValueError(
                f"Invalid arguments for tool '{tool_name}': "
                f"{normalized_arguments}"
            ) from error

    def _validate_arguments(
        self,
        *,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not isinstance(arguments, dict):
            raise ValueError(
                f"Arguments for '{tool_name}' must be a JSON object"
            )

        if tool_name == "list_files":
            folder = arguments.get("folder", ".")

            if not isinstance(folder, str) or not folder.strip():
                raise ValueError(
                    "list_files requires a non-empty string 'folder'"
                )

            return {
                "folder": folder.strip(),
            }

        if tool_name == "read_file":
            file_path = arguments.get("file_path")

            # Some models may still emit "path" despite the schema.
            # Supporting it here makes the tool loop more resilient.
            if file_path is None:
                file_path = arguments.get("path")

            if not isinstance(file_path, str) or not file_path.strip():
                raise ValueError(
                    "read_file requires a non-empty string 'file_path'"
                )

            return {
                "file_path": file_path.strip(),
            }

        raise ValueError(f"Unknown tool: {tool_name}")