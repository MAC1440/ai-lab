from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Iterator, List, Optional


class ConversationNotFoundError(LookupError):
    pass


class ConversationStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def create_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO conversation_sessions (
                    session_id, workspace, agent_id, title, status,
                    rag_top_k, rag_distance_threshold, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session["session_id"], session["workspace"],
                    session["agent_id"], session["title"], session["status"],
                    session["rag_top_k"], session.get("rag_distance_threshold"),
                    session["created_at"], session["updated_at"],
                ),
            )
            connection.commit()
        return self.get_session(session["session_id"])

    def get_session(self, session_id: str) -> Dict[str, Any]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM conversation_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            raise ConversationNotFoundError(
                f"Conversation not found: {session_id}"
            )
        return dict(row)

    def list_sessions(
        self,
        *,
        workspace: str,
        include_archived: bool = False,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if limit < 1 or limit > 200:
            raise ValueError("limit must be between 1 and 200")
        query = "SELECT * FROM conversation_sessions WHERE workspace = ?"
        parameters: List[Any] = [workspace]
        if not include_archived:
            query += " AND status = 'active'"
        query += " ORDER BY updated_at DESC LIMIT ?"
        parameters.append(limit)
        with self._lock, self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def update_session(
        self,
        session_id: str,
        *,
        title: Optional[str] = None,
        status: Optional[str] = None,
        agent_id: Optional[str] = None,
        rag_top_k: Optional[int] = None,
        rag_distance_threshold: Any = ...,
        updated_at: str,
    ) -> Dict[str, Any]:
        current = self.get_session(session_id)
        threshold = (
            current["rag_distance_threshold"]
            if rag_distance_threshold is ...
            else rag_distance_threshold
        )
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE conversation_sessions SET
                    title = ?, status = ?, agent_id = ?, rag_top_k = ?,
                    rag_distance_threshold = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (
                    title if title is not None else current["title"],
                    status if status is not None else current["status"],
                    agent_id if agent_id is not None else current["agent_id"],
                    rag_top_k if rag_top_k is not None else current["rag_top_k"],
                    threshold, updated_at, session_id,
                ),
            )
            connection.commit()
        return self.get_session(session_id)

    def delete_session(self, session_id: str) -> None:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM conversation_sessions WHERE session_id = ?",
                (session_id,),
            )
            if cursor.rowcount == 0:
                raise ConversationNotFoundError(
                    f"Conversation not found: {session_id}"
                )
            connection.commit()

    def add_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock, self._connect() as connection:
            sequence = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM conversation_messages WHERE session_id = ?",
                (message["session_id"],),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO conversation_messages (
                    message_id, session_id, sequence, role, content,
                    agent_result_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message["message_id"], message["session_id"], sequence,
                    message["role"], message["content"],
                    json.dumps(message.get("agent_result"), ensure_ascii=False)
                    if message.get("agent_result") is not None else None,
                    message["created_at"],
                ),
            )
            connection.commit()
        return self.get_message(message["message_id"])

    def get_message(self, message_id: str) -> Dict[str, Any]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM conversation_messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
        if row is None:
            raise LookupError(f"Message not found: {message_id}")
        return self._message(dict(row))

    def list_messages(
        self,
        session_id: str,
        *,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        if limit < 1 or limit > 1000:
            raise ValueError("message limit must be between 1 and 1000")
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM conversation_messages
                WHERE session_id = ? ORDER BY sequence ASC LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [self._message(dict(row)) for row in rows]

    @staticmethod
    def _message(row: Dict[str, Any]) -> Dict[str, Any]:
        raw = row.pop("agent_result_json", None)
        row["agent_result"] = json.loads(raw) if raw else None
        return row

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversation_sessions (
                    session_id TEXT PRIMARY KEY,
                    workspace TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    rag_top_k INTEGER NOT NULL,
                    rag_distance_threshold REAL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    agent_result_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES conversation_sessions(session_id) ON DELETE CASCADE,
                    UNIQUE (session_id, sequence)
                );
                CREATE INDEX IF NOT EXISTS conversation_sessions_workspace_updated
                ON conversation_sessions (workspace, updated_at DESC);
                CREATE INDEX IF NOT EXISTS conversation_messages_session_sequence
                ON conversation_messages (session_id, sequence ASC);
                """
            )
            connection.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()
