from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.agent_service import AgentService
from services.conversation_store import ConversationNotFoundError, ConversationStore
from services.workspace_service import WorkspaceService


class ConversationStateError(RuntimeError):
    pass


class ConversationService:
    def __init__(
        self,
        workspace_service: WorkspaceService,
        agent_service: AgentService,
        store: ConversationStore,
        *,
        max_model_messages: int = 12,
        max_model_history_chars: int = 12_000,
    ) -> None:
        self.workspace_service = workspace_service
        self.agent_service = agent_service
        self.store = store
        self.max_model_messages = max_model_messages
        self.max_model_history_chars = max_model_history_chars

    def create_session(
        self,
        *,
        agent_id: str,
        title: str = "New conversation",
        rag_top_k: int = 3,
        rag_distance_threshold: Optional[float] = 1.0,
    ) -> Dict[str, Any]:
        self.agent_service.get_agent(agent_id)
        if rag_top_k < 1 or rag_top_k > 10:
            raise ValueError("rag_top_k must be between 1 and 10")
        now = self._utc_now()
        session = self.store.create_session(
            {
                "session_id": uuid4().hex,
                "workspace": str(self.workspace_service.get_workspace().resolve()),
                "agent_id": agent_id,
                "title": self._clean_title(title),
                "status": "active",
                "rag_top_k": rag_top_k,
                "rag_distance_threshold": rag_distance_threshold,
                "created_at": now,
                "updated_at": now,
            }
        )
        return self._enrich(session)

    def list_sessions(self, *, include_archived: bool = False) -> List[Dict[str, Any]]:
        workspace = str(self.workspace_service.get_workspace().resolve())
        return [
            self._summary(session)
            for session in self.store.list_sessions(
                workspace=workspace,
                include_archived=include_archived,
            )
        ]

    def get_session(self, session_id: str) -> Dict[str, Any]:
        session = self.store.get_session(self._required_id(session_id))
        self._require_workspace(session)
        return self._enrich(session)

    def update_session(
        self,
        session_id: str,
        *,
        title: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        session = self.get_session(session_id)
        if status is not None and status not in {"active", "archived"}:
            raise ValueError("status must be active or archived")
        updated = self.store.update_session(
            session["session_id"],
            title=self._clean_title(title) if title is not None else None,
            status=status,
            updated_at=self._utc_now(),
        )
        return self._enrich(updated)

    def delete_session(self, session_id: str) -> None:
        session = self.get_session(session_id)
        self.store.delete_session(session["session_id"])

    def prepare_run(
        self,
        *,
        session_id: str,
        agent_id: str,
        prompt: str,
        rag_top_k: int,
        rag_distance_threshold: Optional[float],
    ) -> List[Dict[str, Any]]:
        session = self.get_session(session_id)
        if session["status"] != "active":
            raise ConversationStateError("Archived conversations are read-only")
        if session["agent_id"] != agent_id:
            raise ConversationStateError(
                "The selected agent does not match this conversation"
            )
        history = self.model_history(session_id)
        now = self._utc_now()
        self.store.add_message(
            {
                "message_id": uuid4().hex,
                "session_id": session_id,
                "role": "user",
                "content": prompt,
                "created_at": now,
            }
        )
        title = session["title"]
        if title == "New conversation":
            title = self._title_from_prompt(prompt)
        self.store.update_session(
            session_id,
            title=title,
            agent_id=agent_id,
            rag_top_k=rag_top_k,
            rag_distance_threshold=rag_distance_threshold,
            updated_at=now,
        )
        return history

    def complete_run(
        self,
        *,
        session_id: str,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        session = self.get_session(session_id)
        now = self._utc_now()
        self.store.add_message(
            {
                "message_id": uuid4().hex,
                "session_id": session_id,
                "role": "assistant",
                "content": str(result.get("answer") or ""),
                "agent_result": result,
                "created_at": now,
            }
        )
        self.store.update_session(session["session_id"], updated_at=now)
        return self.get_session(session_id)

    def model_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Return conversation history with reconstructed tool calls and results.

        This preserves the full tool-use context so the model remembers what
        tools it called and what they returned across conversation turns.
        """
        session = self.get_session(session_id)
        messages = session["messages"][-self.max_model_messages :]
        selected: List[Dict[str, Any]] = []
        used = 0

        for message in reversed(messages):
            role = message.get("role")
            content = str(message.get("content", ""))

            if role not in {"user", "assistant"}:
                continue

            # Build this turn's messages in chronological order
            turn_messages: List[Dict[str, Any]] = []
            msg: Dict[str, Any] = {"role": role, "content": content}

            if role == "assistant":
                agent_result = message.get("agent_result")
                if isinstance(agent_result, dict):
                    tools_used = agent_result.get("tools_used", [])
                    if tools_used:
                        tool_calls = []
                        for tool in tools_used:
                            if isinstance(tool, dict):
                                tool_calls.append({
                                    "function": {
                                        "name": tool.get("name", ""),
                                        "arguments": tool.get("arguments", {}),
                                    }
                                })
                        if tool_calls:
                            msg["tool_calls"] = tool_calls

                        for tool in tools_used:
                            if not isinstance(tool, dict):
                                continue
                            tool_name = tool.get("name", "unknown")
                            tool_args = tool.get("arguments", {})
                            tool_status = tool.get("status", "")
                            tool_error = tool.get("error", "")
                            tool_result = tool.get("result")

                            if tool_status == "success":
                                payload = {
                                    "tool": tool_name,
                                    "arguments": tool_args,
                                    "status": "success",
                                    "result": (
                                        tool_result
                                        if tool_result is not None
                                        else "Completed successfully"
                                    ),
                                }
                            else:
                                payload = {
                                    "tool": tool_name,
                                    "arguments": tool_args,
                                    "status": "error",
                                    "error": tool_error or "Unknown error",
                                }

                            tool_content = json.dumps(
                                payload, ensure_ascii=False, default=str
                            )
                            turn_messages.append({
                                "role": "tool",
                                "tool_name": tool_name,
                                "content": tool_content,
                            })

            turn_messages.insert(0, msg)

            # Budget check for the whole turn
            turn_chars = sum(len(m.get("content", "")) for m in turn_messages)
            remaining = self.max_model_history_chars - used
            if remaining <= 0:
                break

            if turn_chars > remaining:
                # Try to fit just the message without tool results
                if len(content) <= remaining:
                    result_msg = {"role": role, "content": content}
                    if role == "assistant" and msg.get("tool_calls"):
                        result_msg["tool_calls"] = msg["tool_calls"]
                    selected.append(result_msg)
                    used += len(content)
                break

            # Add turn messages in reverse order because selected will be
            # reversed at the end to restore chronological order.
            selected.extend(reversed(turn_messages))
            used += turn_chars

        return list(reversed(selected))

    def _enrich(self, session: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(session)
        result["messages"] = self.store.list_messages(session["session_id"])
        result["message_count"] = len(result["messages"])
        return result

    def _summary(self, session: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(session)
        result["message_count"] = len(
            self.store.list_messages(session["session_id"])
        )
        return result

    def _require_workspace(self, session: Dict[str, Any]) -> None:
        active = os.path.normcase(
            str(self.workspace_service.get_workspace().resolve())
        )
        if active != os.path.normcase(session["workspace"]):
            raise ConversationNotFoundError("Conversation not found in this workspace")

    @staticmethod
    def _clean_title(title: str) -> str:
        clean = " ".join(title.strip().split()) if isinstance(title, str) else ""
        if not clean:
            raise ValueError("title cannot be empty")
        return clean[:100]

    @staticmethod
    def _title_from_prompt(prompt: str) -> str:
        clean = " ".join(prompt.strip().split())
        return (clean[:57] + "...") if len(clean) > 60 else clean

    @staticmethod
    def _required_id(value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("session_id must be a non-empty string")
        return value.strip()

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
