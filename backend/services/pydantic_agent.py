from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Collection, Dict, Literal

from pydantic_ai import Agent, ModelRetry, RunContext

from services.agent_service import AgentService
from services.pydantic_model import build_pydantic_model
from tools.file_tools import (
    list_files as _list_files,
    propose_file_change as _propose_file_change,
    propose_file_change_set as _propose_file_change_set,
    propose_path_operation as _propose_path_operation,
    read_file as _read_file,
    read_file_range as _read_file_range,
    search_files as _search_files,
    search_text as _search_text,
)

ToolFunction = Callable[..., Any]
ToolPolicy = Literal["auto", "inspect", "propose"]


@dataclass
class AgentRunDeps:
    """Mutable state that belongs to one Pydantic AI run."""

    tool_policy: ToolPolicy = "auto"
    inspected_paths: set[str] = field(default_factory=set)
    proposed_paths: set[str] = field(default_factory=set)
    change_set_id: str | None = None
    repair_task_id: str | None = None

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


def _normalized_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _run_deps(ctx: RunContext[AgentRunDeps]) -> AgentRunDeps | None:
    return ctx.deps if isinstance(ctx.deps, AgentRunDeps) else None


def list_files(
    ctx: RunContext[AgentRunDeps],
    folder: str = ".",
) -> Any:
    """List files and folders in a workspace directory."""
    del ctx
    try:
        return _list_files(folder or ".")
    except EXPECTED_TOOL_ERRORS as error:
        return _tool_error(error)


def search_files(
    ctx: RunContext[AgentRunDeps],
    query: str,
    folder: str = ".",
    max_results: int = 50,
) -> Any:
    """Find path names; read a returned file before drawing conclusions."""
    del ctx
    try:
        return _search_files(
            query=query,
            folder=folder or ".",
            max_results=max_results,
        )
    except EXPECTED_TOOL_ERRORS as error:
        return _tool_error(error)


def read_file(
    ctx: RunContext[AgentRunDeps],
    file_path: str,
) -> Any:
    """Read a UTF-8 workspace file using its exact relative path."""
    try:
        result = _read_file(file_path)
        deps = _run_deps(ctx)
        if deps is not None and isinstance(result, dict):
            result_path = result.get("path")
            if isinstance(result_path, str):
                deps.inspected_paths.add(_normalized_path(result_path))
        return result
    except EXPECTED_TOOL_ERRORS as error:
        return _tool_error(error)


def read_file_range(
    ctx: RunContext[AgentRunDeps],
    file_path: str,
    start_line: int = 1,
    end_line: int = 200,
) -> Any:
    """Read an inclusive line range from a workspace file."""
    try:
        result = _read_file_range(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
        )
        deps = _run_deps(ctx)
        if deps is not None and isinstance(result, dict):
            result_path = result.get("path")
            if isinstance(result_path, str):
                deps.inspected_paths.add(_normalized_path(result_path))
        return result
    except EXPECTED_TOOL_ERRORS as error:
        return _tool_error(error)


def search_text(
    ctx: RunContext[AgentRunDeps],
    query: str,
    folder: str = ".",
    file_glob: str = "*",
    max_results: int = 50,
) -> Any:
    """Search file contents; read relevant results before proposing changes."""
    del ctx
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
    ctx: RunContext[AgentRunDeps],
    file_path: str,
    new_text: str,
    old_text: str = "",
    summary: str = "",
) -> Any:
    """Create a reviewable proposal after reading the exact target file."""
    deps = _run_deps(ctx)
    normalized_target = _normalized_path(file_path)
    target_exists = True
    try:
        _read_file(file_path)
    except FileNotFoundError:
        target_exists = False
    except EXPECTED_TOOL_ERRORS:
        pass

    if (
        deps is not None
        and deps.tool_policy == "propose"
        and target_exists
        and normalized_target not in deps.inspected_paths
    ):
        raise ModelRetry(
            "Before proposing a change, call read_file or read_file_range "
            f"for the exact target path: {file_path}"
        )

    try:
        result = _propose_file_change(
            file_path=file_path,
            new_text=new_text,
            old_text=old_text,
            summary=summary,
            change_set_id=deps.change_set_id if deps is not None else None,
            repair_task_id=deps.repair_task_id if deps is not None else None,
        )
        if deps is not None:
            deps.proposed_paths.add(normalized_target)
        return result
    except EXPECTED_TOOL_ERRORS as error:
        return _tool_error(error)


def propose_file_change_set(
    ctx: RunContext[AgentRunDeps],
    operations: list[dict[str, str]],
    summary: str = "",
) -> Any:
    """Propose up to 20 related file creates/updates as one change set."""
    deps = _run_deps(ctx)
    try:
        for operation in operations:
            file_path = operation.get("file_path", "")
            normalized = _normalized_path(file_path)
            try:
                _read_file(file_path)
            except FileNotFoundError:
                continue
            except EXPECTED_TOOL_ERRORS:
                # If existence cannot be established, keep the safe default:
                # require an explicit successful read before an update.
                pass
            if deps is not None and normalized not in deps.inspected_paths:
                raise ModelRetry(
                    "Read every existing target before proposing a multi-file "
                    f"change set. Missing read: {file_path}"
                )

        result = _propose_file_change_set(
            operations=operations,
            summary=summary,
            change_set_id=deps.change_set_id if deps is not None else None,
            repair_task_id=deps.repair_task_id if deps is not None else None,
        )
        if deps is not None:
            deps.proposed_paths.update(
                _normalized_path(item.get("file_path", ""))
                for item in operations
                if item.get("file_path")
            )
        return result
    except EXPECTED_TOOL_ERRORS as error:
        return _tool_error(error)


def propose_path_operation(
    ctx: RunContext[AgentRunDeps],
    operation: Literal["delete", "move", "mkdir"],
    file_path: str,
    destination_path: str = "",
    summary: str = "",
) -> Any:
    """Create a reviewed delete, move/rename, or mkdir proposal."""
    deps = _run_deps(ctx)
    normalized_target = _normalized_path(file_path)
    if (
        operation in {"delete", "move"}
        and deps is not None
        and normalized_target not in deps.inspected_paths
    ):
        raise ModelRetry(
            "Read the exact source file before proposing this operation: "
            f"{file_path}"
        )
    try:
        result = _propose_path_operation(
            operation=operation,
            file_path=file_path,
            destination_path=destination_path,
            summary=summary,
            change_set_id=deps.change_set_id if deps is not None else None,
            repair_task_id=deps.repair_task_id if deps is not None else None,
        )
        if deps is not None:
            deps.proposed_paths.add(normalized_target)
        return result
    except EXPECTED_TOOL_ERRORS as error:
        return _tool_error(error)


def enforce_tool_policy(
    ctx: RunContext[AgentRunDeps],
    output: str,
) -> str:
    """Reject a final answer that did not satisfy the requested tool policy."""

    deps = _run_deps(ctx)
    if deps is None or deps.tool_policy == "auto":
        return output

    if deps.tool_policy == "inspect" and not deps.inspected_paths:
        raise ModelRetry(
            "This request requires workspace inspection. Call read_file or "
            "read_file_range on a relevant file before answering."
        )

    if deps.tool_policy == "propose" and not deps.proposed_paths:
        if not deps.inspected_paths:
            raise ModelRetry(
                "This is an enforced repair request. Read the files named in "
                "the failure output, then call propose_file_change or "
                "propose_path_operation. A text-only solution is not accepted."
            )

        inspected = ", ".join(sorted(deps.inspected_paths))
        raise ModelRetry(
            "You inspected workspace files but did not create a reviewable "
            "change. Call the appropriate proposal tool before "
            f"answering. Inspected paths: {inspected}"
        )

    return output


TOOL_FUNCTIONS: Dict[str, ToolFunction] = {
    "list_files": list_files,
    "search_files": search_files,
    "read_file": read_file,
    "read_file_range": read_file_range,
    "search_text": search_text,
    "propose_file_change": propose_file_change,
    "propose_file_change_set": propose_file_change_set,
    "propose_path_operation": propose_path_operation,
}


def _build_pydantic_agent(
    agent_id: str,
    runtime: Dict[str, Any] | None = None,
    toolsets: list[Any] | None = None,
    allowed_tool_names: Collection[str] | None = None,
) -> Agent:
    """Build a Pydantic AI agent from the existing agent configuration."""

    agent_service = AgentService()
    config = agent_service.get_agent(agent_id)

    resolved_tool_names = (
        set(allowed_tool_names)
        if allowed_tool_names is not None
        else agent_service.get_allowed_tool_names(agent_id)
    )

    tools = [
        TOOL_FUNCTIONS[tool_name]
        for tool_name in resolved_tool_names
        if tool_name in TOOL_FUNCTIONS
    ]

    runtime = runtime or {
        "model": config["model"],
        "generation": {
            "temperature": 0.1,
            "max_tokens": 2048,
            "context_window": 8192,
        },
        "provider": {
            "kind": "ollama",
            "base_url": "http://localhost:11434",
        },
    }
    model = build_pydantic_model(runtime)
    generation = runtime["generation"]

    model_settings = {
        "temperature": generation["temperature"],
        "max_tokens": generation["max_tokens"],
    }
    agent = Agent(
        model=model,
        instructions=config["system_prompt"],
        deps_type=AgentRunDeps,
        tools=tools,
        toolsets=toolsets or [],
        retries={"tools": 2, "output": 2},
        model_settings=model_settings,
    )
    agent.output_validator(enforce_tool_policy)
    return agent


@lru_cache(maxsize=10)
def _get_default_pydantic_agent(agent_id: str) -> Agent:
    return _build_pydantic_agent(agent_id)


def get_pydantic_agent(
    agent_id: str,
    runtime: Dict[str, Any] | None = None,
    toolsets: list[Any] | None = None,
    allowed_tool_names: Collection[str] | None = None,
) -> Agent:
    """Use cached defaults, but rebuild when runtime settings are supplied."""

    if runtime is None and not toolsets and allowed_tool_names is None:
        return _get_default_pydantic_agent(agent_id)
    return _build_pydantic_agent(
        agent_id,
        runtime,
        toolsets,
        allowed_tool_names,
    )


get_pydantic_agent.cache_clear = _get_default_pydantic_agent.cache_clear  # type: ignore[attr-defined]
