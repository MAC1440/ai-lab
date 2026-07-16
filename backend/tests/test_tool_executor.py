from unittest.mock import Mock

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
    permissive_agent_service = Mock(spec=AgentService)
    executor = ToolExecutor(
        agent_service=permissive_agent_service
    )

    # Isolate the executor registry branch by making permission validation
    # succeed. The real coding profile deliberately does not permit
    # write_file; model-authored edits must use propose_file_change.
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

    permissive_agent_service.ensure_tool_allowed.assert_called_once_with(
        agent_id="coding",
        tool_name="write_file",
    )
