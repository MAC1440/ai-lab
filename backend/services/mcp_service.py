from __future__ import annotations

import ipaddress
import json
import threading
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator
from pydantic_ai.mcp import MCPToolset


class MCPServerInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=500)
    enabled: bool = False
    tool_prefix: str = Field(default="", max_length=40)
    allowed_tools: list[str] = Field(default_factory=list)
    agent_ids: list[str] = Field(default_factory=list)

    @field_validator("name", "url")
    @classmethod
    def strip_required(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Value cannot be empty")
        return clean

    @field_validator("tool_prefix")
    @classmethod
    def validate_prefix(cls, value: str) -> str:
        clean = value.strip().lower().replace("-", "_")
        if clean and not clean.replace("_", "").isalnum():
            raise ValueError("Tool prefix may only contain letters, numbers, and _")
        return clean


class MCPService:
    """Own the small, explicitly allowlisted MCP configuration."""

    def __init__(self, settings_path: str | Path) -> None:
        self.settings_path = Path(settings_path)
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if not self.settings_path.exists():
            self._write({"version": 1, "servers": {}})

    def snapshot(self) -> Dict[str, Any]:
        return {"servers": list(self._read()["servers"].values())}

    def save_server(
        self,
        server_id: str,
        request: MCPServerInput,
        *,
        valid_agent_ids: set[str],
    ) -> Dict[str, Any]:
        self._validate_id(server_id)
        unknown_agents = sorted(set(request.agent_ids) - valid_agent_ids)
        if unknown_agents:
            raise ValueError("Unknown agents: " + ", ".join(unknown_agents))
        server = {
            "id": server_id,
            "name": request.name.strip(),
            "url": self._validate_url(request.url),
            "enabled": request.enabled,
            "tool_prefix": request.tool_prefix or server_id.replace("-", "_"),
            "allowed_tools": sorted(
                {item.strip() for item in request.allowed_tools if item.strip()}
            ),
            "agent_ids": sorted(set(request.agent_ids)),
        }
        with self._lock:
            document = self._read()
            document["servers"][server_id] = server
            self._write(document)
        return server

    def delete_server(self, server_id: str) -> None:
        with self._lock:
            document = self._read()
            if server_id not in document["servers"]:
                raise ValueError(f"Unknown MCP server: {server_id}")
            del document["servers"][server_id]
            self._write(document)

    async def discover_tools(self, server_id: str) -> Dict[str, Any]:
        server = self._get_server(server_id)
        toolset = MCPToolset(
            server["url"], init_timeout=10.0, read_timeout=15.0
        )
        try:
            async with toolset:
                raw_tools = await toolset.list_tools()
        except Exception as error:
            raise RuntimeError(
                f"Could not connect to MCP server '{server['name']}': {error}"
            ) from error

        tools = []
        for tool in raw_tools:
            annotations = getattr(tool, "annotations", None)
            if hasattr(annotations, "model_dump"):
                annotations = annotations.model_dump(exclude_none=True)
            elif not isinstance(annotations, dict):
                annotations = {}
            safe, safety_reason = self._tool_is_read_only(
                tool.name, annotations
            )
            tools.append(
                {
                    "name": tool.name,
                    "description": getattr(tool, "description", None) or "",
                    "annotations": annotations,
                    "currently_allowed": tool.name in server["allowed_tools"],
                    "safe_to_enable": safe,
                    "safety_reason": safety_reason,
                }
            )
        return {"server": server, "tools": tools}

    async def test_server(self, server_id: str) -> Dict[str, Any]:
        result = await self.discover_tools(server_id)
        return {
            **result,
            "ok": True,
            "message": f"Connected successfully; found {len(result['tools'])} tool(s).",
        }

    def build_toolsets(self, agent_id: str) -> list[Any]:
        toolsets: list[Any] = []
        for server in self._read()["servers"].values():
            if not server["enabled"] or agent_id not in server["agent_ids"]:
                continue
            allowed = frozenset(server["allowed_tools"])
            if not allowed:
                continue

            def allow_tool(
                ctx: Any,
                tool: Any,
                names: frozenset[str] = allowed,
            ) -> bool:
                del ctx
                metadata = getattr(tool, "metadata", {}) or {}
                annotations = metadata.get("annotations", {})
                safe, _ = self._tool_is_read_only(tool.name, annotations)
                return tool.name in names and safe

            toolset: Any = MCPToolset(
                server["url"],
                id=server["id"],
                init_timeout=10.0,
                read_timeout=30.0,
                include_instructions=False,
            ).filtered(allow_tool)
            prefix = server.get("tool_prefix")
            if prefix:
                toolset = toolset.prefixed(prefix)
            toolsets.append(toolset)
        return toolsets

    def _get_server(self, server_id: str) -> Dict[str, Any]:
        server = self._read()["servers"].get(server_id)
        if server is None:
            raise ValueError(f"Unknown MCP server: {server_id}")
        return dict(server)

    def _read(self) -> Dict[str, Any]:
        with self._lock:
            try:
                document = json.loads(self.settings_path.read_text("utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise RuntimeError(f"Could not read MCP settings: {error}") from error
            document.setdefault("servers", {})
            return document

    def _write(self, document: Dict[str, Any]) -> None:
        with self._lock:
            temporary = self.settings_path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.settings_path)

    @staticmethod
    def _validate_id(server_id: str) -> None:
        if not server_id or any(
            char not in "abcdefghijklmnopqrstuvwxyz0123456789-_"
            for char in server_id
        ):
            raise ValueError(
                "Server id may only contain lowercase letters, numbers, - and _"
            )

    @staticmethod
    def _validate_url(value: str) -> str:
        clean = value.strip().rstrip("/")
        parsed = urlparse(clean)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("MCP URL must be a valid http:// or https:// URL")
        if parsed.username or parsed.password:
            raise ValueError("Do not put credentials inside the MCP URL")
        host = parsed.hostname.lower()
        is_loopback = host == "localhost"
        try:
            is_loopback = is_loopback or ipaddress.ip_address(host).is_loopback
        except ValueError:
            pass
        if not is_loopback and parsed.scheme != "https":
            raise ValueError("Remote MCP servers must use HTTPS")
        return clean

    @staticmethod
    def _tool_is_read_only(
        name: str, annotations: Dict[str, Any]
    ) -> tuple[bool, str]:
        lower = name.lower().replace("-", "_")
        if annotations.get("destructiveHint") is True:
            return False, "Server marks this tool as destructive."
        if annotations.get("readOnlyHint") is False:
            return False, "Server marks this tool as capable of mutation."
        blocked_words = {
            "write", "create", "delete", "remove", "edit", "update",
            "move", "rename", "execute", "exec", "shell", "command",
            "apply", "patch", "send", "publish", "upload",
        }
        name_words = set(lower.split("_"))
        if name_words.intersection(blocked_words):
            return False, "Tool name indicates a mutating operation."
        if annotations.get("readOnlyHint") is True:
            return True, "Server marks this tool read-only."
        read_prefixes = (
            "read", "get", "list", "search", "find", "fetch", "query",
            "lookup", "resolve", "inspect", "describe",
        )
        if lower.startswith(read_prefixes):
            return True, "Tool name matches the conservative read-only allowlist."
        return False, "Tool is not explicitly identifiable as read-only."
