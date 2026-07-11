import json
from typing import Any, Dict, List, Optional

from services.agent_service import AgentService
from services.ollama_client import OllamaClient
from services.tool_executor import ToolExecutor
from services.tool_registry import READ_ONLY_TOOL_SCHEMAS


class AgentRunner:
    def __init__(
        self,
        agent_service: Optional[AgentService] = None,
        tool_executor: Optional[ToolExecutor] = None,
        max_steps: int = 8,
    ):
        self.agent_service = agent_service or AgentService()
        self.tool_executor = tool_executor or ToolExecutor(
            self.agent_service
        )
        self.max_steps = max_steps

    def run(
        self,
        *,
        agent_id: str,
        prompt: str,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        agent = self.agent_service.get_agent(agent_id)

        client = OllamaClient(
            model=agent["model"],
        )

        messages: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": self._build_system_prompt(agent),
            }
        ]

        if history:
            messages.extend(history)

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        executed_tools: List[Dict[str, Any]] = []

        for step in range(1, self.max_steps + 1):
            response = client.chat_with_tools(
                messages=messages,
                tools=READ_ONLY_TOOL_SCHEMAS,
                options={
                    "temperature": 0.1,
                    "num_predict": 1024,
                },
            )

            assistant_message = response.get("message", {})
            messages.append(assistant_message)

            tool_calls = assistant_message.get("tool_calls") or []

            if not tool_calls:
                return {
                    "answer": assistant_message.get("content", ""),
                    "agent_id": agent_id,
                    "model": client.model,
                    "steps": step,
                    "tools_used": executed_tools,
                }

            for tool_call in tool_calls:
                function_data = tool_call.get("function", {})

                tool_name = function_data.get("name")
                arguments = function_data.get("arguments", {})

                if not tool_name:
                    raise ValueError(
                        "The model returned a tool call without a name."
                    )

                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError as error:
                        raise ValueError(
                            f"Invalid JSON arguments returned for '{tool_name}'"
                        ) from error

                if not isinstance(arguments, dict):
                    raise ValueError(
                        f"Tool arguments for '{tool_name}' must be an object."
                    )

                try:
                    tool_result = self.tool_executor.execute(
                        agent_id=agent_id,
                        tool_name=tool_name,
                        arguments=arguments,
                    )

                    tool_result_content = json.dumps(
                        tool_result,
                        ensure_ascii=False,
                    )

                    executed_tools.append(
                        {
                            "name": tool_name,
                            "arguments": arguments,
                            "status": "success",
                        }
                    )

                except Exception as error:
                    tool_result_content = json.dumps(
                        {
                            "error": str(error),
                        },
                        ensure_ascii=False,
                    )

                    executed_tools.append(
                        {
                            "name": tool_name,
                            "arguments": arguments,
                            "status": "error",
                            "error": str(error),
                        }
                    )

                messages.append(
                    {
                        "role": "tool",
                        "tool_name": tool_name,
                        "content": tool_result_content,
                    }
                )

        return {
            "answer": (
                "The agent reached the maximum number of tool steps "
                "before completing the task."
            ),
            "agent_id": agent_id,
            "model": client.model,
            "steps": self.max_steps,
            "tools_used": executed_tools,
        }

    def _build_system_prompt(
        self,
        agent: Dict[str, Any],
    ) -> str:
        return f"""
{agent["system_prompt"]}

You have access to tools for inspecting the currently selected workspace.

Rules:
- Use list_files when you need to discover available files or folders.
- Use read_file when you need the exact contents of a file.
- Never claim you inspected a file unless you actually used a tool.
- Never invent file names or file contents.
- You currently have read-only access.
- Do not claim to create, edit, rename, delete, or overwrite files.
- Use relative paths inside the selected workspace.
- When you have enough information, stop calling tools and answer the user.
""".strip()