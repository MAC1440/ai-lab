from typing import Any, Dict, List


AGENTS: Dict[str, Dict[str, Any]] = {
    "general": {
        "id": "general",
        "name": "General Assistant",
        "description": "General-purpose local assistant.",
        "model": "llama3.2:3b",
        "system_prompt": (
            "You are a helpful personal assistant. "
            "Give direct, accurate and concise answers."
        ),
        "use_rag": False,
        "tools": [],
    },
    "unity": {
        "id": "unity",
        "name": "Unity Assistant",
        "description": "Answers Unity questions using indexed documentation.",
        "model": "llama3.2:3b",
        "system_prompt": (
            "You are a Unity development assistant. "
            "Prefer the retrieved Unity documentation when it is relevant. "
            "Clearly distinguish documented facts from general model knowledge."
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
        "description": "Inspects and assists with the selected code workspace.",
        "model": "qwen2.5-coder:3b",
        "system_prompt": (
            "You are a careful senior software engineer. "
            "Inspect the available project context before suggesting changes. "
            "Do not claim that a file was changed unless a tool actually changed it."
        ),
        "use_rag": False,
        "tools": [
            "list_files",
            "read_file",
        ],
    },
}


class AgentService:
    def list_agents(self) -> List[Dict[str, Any]]:
        return list(AGENTS.values())

    def get_agent(self, agent_id: str) -> Dict[str, Any]:
        agent = AGENTS.get(agent_id)

        if agent is None:
            raise ValueError(f"Unknown agent: {agent_id}")

        return agent