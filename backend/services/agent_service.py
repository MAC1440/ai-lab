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
            "Give accurate, direct, and concise answers."
        ),
        "use_rag": False,
        "tools": [],
    },
    "unity": {
        "id": "unity",
        "name": "Unity Assistant",
        "description": (
            "A Unity assistant that can inspect local files and use "
            "indexed Unity documentation."
        ),
        "model": "qwen3:4b",
        "system_prompt": (
            "You are a Unity development assistant. "
            "Use local project files and retrieved Unity documentation "
            "when relevant. Clearly distinguish documentation, project "
            "code, and general model knowledge."
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
        "description": (
            "A coding assistant that can inspect the selected workspace."
        ),

        # Important:
        # qwen2.5-coder:3b is useful for code generation but has unreliable
        # native tool calling through Ollama. Qwen 3 is used for now because
        # this route requires reliable tool_calls.
        "model": "qwen3:4b",

        "system_prompt": (
            "You are a careful senior software engineer. "
            "Inspect relevant project files before drawing conclusions. "
            "Never claim that you read or modified a file unless a tool "
            "actually performed that action."
        ),
        "use_rag": False,
        "tools": [
            "list_files",
            "read_file",

            # The permission remains available for the manually tested route,
            # but write_file is intentionally not sent to the LLM yet.
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

    def get_allowed_tool_names(self, agent_id: str) -> List[str]:
        agent = self.get_agent(agent_id)
        return list(agent.get("tools", []))

    def is_tool_allowed(
        self,
        agent_id: str,
        tool_name: str,
    ) -> bool:
        return tool_name in self.get_allowed_tool_names(agent_id)

    def ensure_tool_allowed(
        self,
        agent_id: str,
        tool_name: str,
    ) -> None:
        if not self.is_tool_allowed(agent_id, tool_name):
            raise PermissionError(
                f"Agent '{agent_id}' is not allowed to use "
                f"tool '{tool_name}'"
            )