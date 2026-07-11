import json
from typing import Any, Dict, List, Optional

from services.agent_service import AgentService
from services.ollama_client import OllamaClient
from services.tool_executor import ToolExecutor
from services.tool_registry import get_tool_schemas


Message = Dict[str, Any]


EXPECTED_TOOL_ERRORS = (
    FileNotFoundError,
    NotADirectoryError,
    IsADirectoryError,
    PermissionError,
    UnicodeDecodeError,
    ValueError,
    RuntimeError,
)


class AgentRunner:
    def __init__(
        self,
        agent_service: Optional[AgentService] = None,
        tool_executor: Optional[ToolExecutor] = None,
        max_steps: int = 6,
    ):
        self.agent_service = (
            agent_service
            or AgentService()
        )

        self.tool_executor = (
            tool_executor
            or ToolExecutor(self.agent_service)
        )

        self.max_steps = max_steps

    def run(
        self,
        *,
        agent_id: str,
        prompt: str,
        history: Optional[List[Message]] = None,
    ) -> Dict[str, Any]:
        clean_prompt = prompt.strip()

        if not clean_prompt:
            raise ValueError("Prompt cannot be empty")

        agent = self.agent_service.get_agent(agent_id)

        client = OllamaClient(
            model=agent["model"],
        )

        allowed_tool_names = (
            self.agent_service.get_allowed_tool_names(agent_id)
        )

        tool_schemas = get_tool_schemas(
            allowed_tool_names
        )

        messages: List[Message] = [
            {
                "role": "system",
                "content": self._build_system_prompt(
                    agent=agent,
                    has_tools=bool(tool_schemas),
                ),
            }
        ]

        messages.extend(
            self._sanitize_history(history)
        )

        messages.append(
            {
                "role": "user",
                "content": clean_prompt,
            }
        )

        executed_tools: List[Dict[str, Any]] = []

        for step in range(1, self.max_steps + 1):
            response = client.chat_with_tools(
                messages=messages,
                tools=tool_schemas,
                options={
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "num_predict": 1024,
                    "num_ctx": 4096,
                },
            )

            assistant_message = response.get(
                "message",
                {},
            )

            content = assistant_message.get(
                "content",
                "",
            )

            if not isinstance(content, str):
                content = str(content or "")

            raw_tool_calls = assistant_message.get(
                "tool_calls",
                [],
            )

            if not isinstance(raw_tool_calls, list):
                raise RuntimeError(
                    "Ollama returned 'tool_calls' in an "
                    "unexpected format"
                )

            # Keep only fields Ollama expects when the message is sent
            # back in the next loop iteration.
            stored_assistant_message: Message = {
                "role": "assistant",
                "content": content,
            }

            if raw_tool_calls:
                stored_assistant_message["tool_calls"] = (
                    raw_tool_calls
                )

            messages.append(stored_assistant_message)

            if not raw_tool_calls:
                final_answer = content.strip()

                if not final_answer:
                    raise RuntimeError(
                        f"Model '{client.model}' returned neither "
                        "a text answer nor a valid tool call. "
                        "This commonly happens when a model does "
                        "not reliably support Ollama tool calling."
                    )

                return {
                    "answer": final_answer,
                    "agent_id": agent_id,
                    "model": client.model,
                    "steps": step,
                    "tools_used": executed_tools,
                }

            for tool_call in raw_tool_calls:
                tool_name, arguments = (
                    self._parse_tool_call(tool_call)
                )

                tool_record: Dict[str, Any] = {
                    "name": tool_name,
                    "arguments": arguments,
                }

                try:
                    tool_result = (
                        self.tool_executor.execute(
                            agent_id=agent_id,
                            tool_name=tool_name,
                            arguments=arguments,
                        )
                    )

                    tool_record["status"] = "success"

                    tool_result_content = json.dumps(
                        tool_result,
                        ensure_ascii=False,
                        default=str,
                    )

                except EXPECTED_TOOL_ERRORS as error:
                    tool_record["status"] = "error"
                    tool_record["error"] = str(error)

                    tool_result_content = json.dumps(
                        {
                            "error": str(error),
                            "tool": tool_name,
                            "arguments": arguments,
                        },
                        ensure_ascii=False,
                    )

                executed_tools.append(tool_record)

                messages.append(
                    {
                        "role": "tool",
                        "tool_name": tool_name,
                        "content": tool_result_content,
                    }
                )

        raise RuntimeError(
            "The agent reached the maximum number of tool "
            f"steps ({self.max_steps}) without producing a "
            "final answer."
        )

    def _parse_tool_call(
        self,
        tool_call: Any,
    ) -> tuple[str, Dict[str, Any]]:
        if not isinstance(tool_call, dict):
            raise RuntimeError(
                "Ollama returned an invalid tool call"
            )

        function_data = tool_call.get(
            "function",
            {},
        )

        if not isinstance(function_data, dict):
            raise RuntimeError(
                "Ollama returned a tool call without a "
                "valid function object"
            )

        tool_name = function_data.get("name")

        if not isinstance(tool_name, str) or not tool_name:
            raise RuntimeError(
                "Ollama returned a tool call without a "
                "valid function name"
            )

        arguments = function_data.get(
            "arguments",
            {},
        )

        # Some Ollama/model combinations return arguments as a JSON string.
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as error:
                raise RuntimeError(
                    f"Model returned invalid JSON arguments "
                    f"for tool '{tool_name}': {arguments}"
                ) from error

        if not isinstance(arguments, dict):
            raise RuntimeError(
                f"Tool arguments for '{tool_name}' must be "
                "a JSON object"
            )

        return tool_name, arguments

    def _sanitize_history(
        self,
        history: Optional[List[Message]],
    ) -> List[Message]:
        if not history:
            return []

        sanitized: List[Message] = []

        for message in history:
            if not isinstance(message, dict):
                continue

            role = message.get("role")
            content = message.get("content")

            # System and tool messages must only originate from the backend.
            if role not in {"user", "assistant"}:
                continue

            if not isinstance(content, str):
                continue

            if not content.strip():
                continue

            sanitized.append(
                {
                    "role": role,
                    "content": content,
                }
            )

        # Prevent unrestricted growth for now.
        return sanitized[-12:]

    def _build_system_prompt(
        self,
        *,
        agent: Dict[str, Any],
        has_tools: bool,
    ) -> str:
        base_prompt = agent.get(
            "system_prompt",
            "You are a helpful assistant.",
        )

        if not has_tools:
            return base_prompt

        return f"""
{base_prompt}

You are operating inside a tool-use loop.

Available behavior:
- Use list_files to discover project files and folders.
- Use read_file to inspect the exact content of a text file.
- You may call several tools across multiple steps.
- Use paths relative to the selected workspace.
- Prefer paths returned by list_files.
- Do not invent file names or file contents.
- Never claim you inspected a file unless read_file succeeded.
- You currently have read-only access through this agent route.
- Do not claim to create, edit, delete, rename, or overwrite files.
- Once you have enough evidence, stop calling tools and provide a direct final answer.
""".strip()