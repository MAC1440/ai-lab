from unittest.mock import Mock

import pytest

from services.agent_service import AgentService
from services.tool_executor import ToolExecutor


def test_general_agent_cannot_read_files():
    executor = ToolExecutor(
        agent_service=AgentService()
    )

    with pytest.raises(PermissionError):
        executor.execute(
            agent_id="general",
            tool_name="read_file",
            arguments={
                "file_path": "backend/main.py",
            },
        )


def test_unknown_tool_is_rejected():
    executor = ToolExecutor(
        agent_service=AgentService()
    )

    with pytest.raises(ValueError):
        executor.execute(
            agent_id="coding",
            tool_name="delete_everything",
            arguments={},
        )