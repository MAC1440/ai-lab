from functools import lru_cache
from typing import Any, Callable, Dict

from pydantic_ai import Agent

from services.agent_service import AgentService
from services.pydantic_model import get_ollama_model
from tools.file_tools import (
    list_files as _list_files,
    propose_file_change as _propose_file_change,
    read_file as _read_file,
    read_file_range as _read_file_range,
    search_files as _search_files,
    search_text as _search_text,
)

ToolFunction = Callable[..., Any]



EXPECTED_TOOL_ERRORS = (
    FileNotFoundError,
    NotADirectoryError,
    IsADirectoryError,
    PermissionError,
    UnicodeDecodeError,
    ValueError,
    RuntimeError,
    OSError,
)


def _tool_error(error: Exception) -> Dict[str, str]:
    return {
        "error": str(error),
        "error_type": type(error).__name__,
    }


def list_files(folder: str = ".") -> Any:
    """List files and folders in a workspace directory."""
    try:
        return _list_files(folder or ".")
    except EXPECTED_TOOL_ERRORS as error:
        return _tool_error(error)


def search_files(
    query: str,
    folder: str = ".",
    max_results: int = 50,
) -> Any:
    """Find workspace paths containing the supplied name fragment."""
    try:
        return _search_files(
            query=query,
            folder=folder or ".",
            max_results=max_results,
        )
    except EXPECTED_TOOL_ERRORS as error:
        return _tool_error(error)


def read_file(file_path: str) -> Any:
    """Read a UTF-8 workspace file using its exact relative path."""
    try:
        return _read_file(file_path)
    except EXPECTED_TOOL_ERRORS as error:
        return _tool_error(error)


def read_file_range(
    file_path: str,
    start_line: int = 1,
    end_line: int = 200,
) -> Any:
    """Read an inclusive line range from a workspace file."""
    try:
        return _read_file_range(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
        )
    except EXPECTED_TOOL_ERRORS as error:
        return _tool_error(error)


def search_text(
    query: str,
    folder: str = ".",
    file_glob: str = "*",
    max_results: int = 50,
) -> Any:
    """Search text inside workspace files."""
    try:
        return _search_text(
            query=query,
            folder=folder or ".",
            file_glob=file_glob,
            max_results=max_results,
        )
    except EXPECTED_TOOL_ERRORS as error:
        return _tool_error(error)


def propose_file_change(
    file_path: str,
    new_text: str,
    old_text: str = "",
    summary: str = "",
) -> Any:
    """Create a reviewable file-change proposal without writing it."""
    try:
        return _propose_file_change(
            file_path=file_path,
            new_text=new_text,
            old_text=old_text,
            summary=summary,
        )
    except EXPECTED_TOOL_ERRORS as error:
        return _tool_error(error)
    

TOOL_FUNCTIONS: Dict[str, ToolFunction] = {
    "list_files": list_files,
    "search_files": search_files,
    "read_file": read_file,
    "read_file_range": read_file_range,
    "search_text": search_text,
    "propose_file_change": propose_file_change,
}
@lru_cache(maxsize=10)
def get_pydantic_agent(agent_id: str) -> Agent:
    """Build a Pydantic AI agent from the existing agent configuration."""

    agent_service = AgentService()
    config = agent_service.get_agent(agent_id)

    allowed_tool_names = agent_service.get_allowed_tool_names(agent_id)

    tools = [
        TOOL_FUNCTIONS[tool_name]
        for tool_name in allowed_tool_names
        if tool_name in TOOL_FUNCTIONS
    ]

    model = get_ollama_model(config["model"])

    return Agent(
        model=model,
        instructions=config["system_prompt"],
        tools=tools,
        model_settings={
            "temperature": 0.1,
            "max_tokens": 1024,
        },
    )