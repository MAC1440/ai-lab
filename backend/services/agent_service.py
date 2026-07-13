from typing import Any, Dict, List


AgentConfig = Dict[str, Any]


AGENTS: Dict[str, AgentConfig] = {
    "general": {
        "id": "general",
        "name": "General Assistant",
        "description": "A general-purpose local assistant.",
        "model": "granite4.1:3b",
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
        "model": "granite4.1:3b",
        "system_prompt": (
            "You are a Unity development assistant. "
            "Use local project files and retrieved Unity documentation "
            "when relevant. Clearly distinguish documentation, project "
            "code, and general model knowledge."
        ),
        "use_rag": True,
        "tools": [
            "list_files",
            "search_files",
            "read_file",
            "read_file_range",
            "search_text",
        ],
    },
    "coding": {
        "id": "coding",
        "name": "Coding Agent",
        "description": (
            "A coding assistant that can inspect the selected workspace "
            "and prepare reviewable file-change proposals."
        ),
        "model": "granite4.1:3b",
        "system_prompt": (
            "You are a careful senior software engineer. "
            "Inspect the relevant project files before drawing conclusions. "
            "Use search tools to locate symbols and read tools to verify the "
            "exact current code. When the user asks for a code change, call "
            "propose_file_change after reading the target file. Prefer a small "
            "exact unique old_text plus its replacement new_text. If producing "
            "the complete corrected file is easier, omit old_text and send the "
            "entire file as new_text. If the proposal tool returns an argument "
            "error, correct the arguments and retry it once instead of only "
            "printing corrected code in chat. propose_file_change creates a "
            "reviewable diff and does not write the file; a human must approve "
            "it first. Never claim that you read, changed, proposed, or applied "
            "a file unless the corresponding tool actually succeeded."
        ),
        "use_rag": False,
        "tools": [
            "list_files",
            "search_files",
            "read_file",
            "read_file_range",
            "search_text",
            "propose_file_change",
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

    def is_tool_allowed(self, agent_id: str, tool_name: str) -> bool:
        return tool_name in self.get_allowed_tool_names(agent_id)

    def ensure_tool_allowed(self, agent_id: str, tool_name: str) -> None:
        if not self.is_tool_allowed(agent_id, tool_name):
            raise PermissionError(
                f"Agent '{agent_id}' is not allowed to use "
                f"tool '{tool_name}'"
            )