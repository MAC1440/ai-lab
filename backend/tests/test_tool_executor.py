import pytest

from services.agent_service import AgentService
from services.tool_executor import ToolExecutor


def test_general_agent_cannot_read_files():
    executor = ToolExecutor(
        agent_service=AgentService()
    )

    with pytest.raises(
        PermissionError,
        match="is not allowed to use tool 'read_file'",
    ):
        executor.execute(
            agent_id="general",
            tool_name="read_file",
            arguments={
                "file_path": "backend/main.py",
            },
        )


def test_unknown_unpermitted_tool_is_rejected():
    executor = ToolExecutor(
        agent_service=AgentService()
    )

    # Permission checking occurs before registry lookup.
    #
    # delete_everything is not included in the coding agent's
    # permissions, so PermissionError is the expected result.
    with pytest.raises(
        PermissionError,
        match="is not allowed to use tool 'delete_everything'",
    ):
        executor.execute(
            agent_id="coding",
            tool_name="delete_everything",
            arguments={},
        )


def test_allowed_but_unavailable_tool_is_rejected():
    executor = ToolExecutor(
        agent_service=AgentService()
    )

    # The coding profile still has write_file permission, but
    # write_file is intentionally not registered as model-callable.
    #
    # It passes permission validation and then fails the executor
    # registry lookup with ValueError.
    with pytest.raises(
        ValueError,
        match="Tool 'write_file' is not available",
    ):
        executor.execute(
            agent_id="coding",
            tool_name="write_file",
            arguments={
                "file_path": "example.py",
                "content": "print('hello')",
            },
        )