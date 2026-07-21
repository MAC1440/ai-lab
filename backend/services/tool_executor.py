from typing import Any, Callable, Dict

from services.agent_service import AgentService
from tools.file_tools import (
    list_files,
    propose_file_change,
    propose_file_change_set,
    propose_path_operation,
    read_file,
    read_file_range,
    search_files,
    search_text,
)

ToolFunction = Callable[..., Any]


class ToolExecutor:
    def __init__(
        self,
        agent_service: AgentService | None = None,
    ):
        self.agent_service = agent_service or AgentService()
        self._tools: Dict[str, ToolFunction] = {
            "list_files": list_files,
            "search_files": search_files,
            "read_file": read_file,
            "read_file_range": read_file_range,
            "search_text": search_text,
            "propose_file_change": propose_file_change,
            "propose_file_change_set": propose_file_change_set,
            "propose_path_operation": propose_path_operation,
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
            return {
                "folder": self._string(arguments, "folder", default="."),
            }

        if tool_name == "search_files":
            return {
                "query": self._string(arguments, "query"),
                "folder": self._string(arguments, "folder", default="."),
                "max_results": self._integer(
                    arguments,
                    "max_results",
                    default=50,
                    minimum=1,
                    maximum=200,
                ),
            }

        if tool_name == "read_file":
            return {
                "file_path": self._file_path(arguments),
            }

        if tool_name == "read_file_range":
            return {
                "file_path": self._file_path(arguments),
                "start_line": self._integer(
                    arguments,
                    "start_line",
                    default=1,
                    minimum=1,
                ),
                "end_line": self._integer(
                    arguments,
                    "end_line",
                    default=200,
                    minimum=1,
                ),
            }

        if tool_name == "search_text":
            return {
                "query": self._string(arguments, "query"),
                "folder": self._string(arguments, "folder", default="."),
                "file_glob": self._string(
                    arguments,
                    "file_glob",
                    default="*",
                ),
                "max_results": self._integer(
                    arguments,
                    "max_results",
                    default=50,
                    minimum=1,
                    maximum=200,
                ),
            }

        if tool_name == "propose_file_change":
            old_text = arguments.get("old_text", "")
            new_text = arguments.get("new_text", arguments.get("content"))

            if not isinstance(old_text, str):
                raise ValueError(
                    "propose_file_change 'old_text' must be a string when supplied"
                )
            if not isinstance(new_text, str):
                raise ValueError(
                    "propose_file_change requires string 'new_text'"
                )

            return {
                "file_path": self._file_path(arguments),
                "old_text": old_text,
                "new_text": new_text,
                "summary": self._string(
                    arguments,
                    "summary",
                    default="",
                    allow_empty=True,
                ),
            }

        if tool_name == "propose_file_change_set":
            operations = arguments.get("operations")
            if not isinstance(operations, list):
                raise ValueError(
                    "propose_file_change_set requires an operations array"
                )
            return {
                "operations": operations,
                "summary": self._string(
                    arguments,
                    "summary",
                    default="",
                    allow_empty=True,
                ),
            }

        if tool_name == "propose_path_operation":
            return {
                "operation": self._string(arguments, "operation"),
                "file_path": self._file_path(arguments),
                "destination_path": self._string(
                    arguments,
                    "destination_path",
                    default="",
                    allow_empty=True,
                ),
                "summary": self._string(
                    arguments,
                    "summary",
                    default="",
                    allow_empty=True,
                ),
            }

        raise ValueError(f"Unknown tool: {tool_name}")

    @staticmethod
    def _file_path(arguments: Dict[str, Any]) -> str:
        value = arguments.get("file_path", arguments.get("path"))
        if not isinstance(value, str) or not value.strip():
            raise ValueError("A non-empty string 'file_path' is required")
        return value.strip()

    @staticmethod
    def _string(
        arguments: Dict[str, Any],
        name: str,
        *,
        default: str | None = None,
        allow_empty: bool = False,
    ) -> str:
        value = arguments.get(name, default)
        if not isinstance(value, str):
            raise ValueError(f"{name} must be a string")
        if not allow_empty and not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
        return value.strip() if not allow_empty else value

    @staticmethod
    def _integer(
        arguments: Dict[str, Any],
        name: str,
        *,
        default: int,
        minimum: int,
        maximum: int | None = None,
    ) -> int:
        value = arguments.get(name, default)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{name} must be an integer")
        if value < minimum:
            raise ValueError(f"{name} must be at least {minimum}")
        if maximum is not None and value > maximum:
            raise ValueError(f"{name} must be at most {maximum}")
        return value
