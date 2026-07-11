from typing import Any, Dict, List


AgentConfig = Dict[str, Any]


AGENTS: Dict[str, AgentConfig] = {
    "general": {
        "id": "general",
        "name": "General Assistant",
        "description": "A general-purpose local assistant.",
        "model": "qwen3:4b",
        "system_prompt": (
            "You are a helpful personal assistant. "
            "Give accurate, direct and concise answers."
        ),
        "use_rag": False,
        "tools": [],
    },
    "unity": {
        "id": "unity",
        "name": "Unity Assistant",
        "description": "A Unity assistant grounded in indexed documentation.",
        "model": "qwen3:4b",
        "system_prompt": (
            "You are a Unity development assistant. "
            "Use retrieved Unity documentation whenever it is relevant. "
            "Clearly distinguish documentation from general knowledge."
        ),
        "use_rag": True,
        "tools": [
            "list_files",
            "read_file",
        ],
    },
    "coding": {
        "id": "coding",
        "name": "Coding Agent",
        "description": "A coding assistant that can inspect the selected workspace.",
        "model": "qwen2.5-coder:3b",
        "system_prompt": (
            "You are a careful senior software engineer. "
            "Inspect project files before suggesting changes. "
            "Never claim that a file was modified unless a tool actually modified it."
        ),
        "use_rag": False,
        "tools": [
            "list_files",
            "read_file",
            "write_file",
        ],
    },
}


class AgentService:
    def list_agents(self) -> List[AgentConfig]:
        return list(AGENTS.values())

    def get_agent(self, agent_id: str) -> AgentConfig:
        agent = AGENTS.get(agent_id)

        if agent is None:
            raise ValueError(f"Unknown agent: {agent_id}")

        return agent

    def is_tool_allowed(
        self,
        agent_id: str,
        tool_name: str,
    ) -> bool:
        agent = self.get_agent(agent_id)
        allowed_tools = agent.get("tools", [])

        return tool_name in allowed_tools

    def ensure_tool_allowed(
        self,
        agent_id: str,
        tool_name: str,
    ) -> None:
        if not self.is_tool_allowed(agent_id, tool_name):
            raise PermissionError(
                f"Agent '{agent_id}' is not allowed to use '{tool_name}'"
            )