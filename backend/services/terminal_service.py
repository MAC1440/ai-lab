from __future__ import annotations

import asyncio
import importlib.util
import os
import re
import shutil
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Deque, Dict, Optional, Protocol
from uuid import uuid4

from services.workspace_service import WorkspaceService


DEFAULT_COLUMNS = 120
DEFAULT_ROWS = 32
MIN_COLUMNS = 20
MAX_COLUMNS = 300
MIN_ROWS = 5
MAX_ROWS = 200
MAX_INPUT_CHARACTERS = 32_768
MAX_RESUME_ID_CHARACTERS = 160
RESUME_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]+$")


class TerminalUnavailableError(RuntimeError):
    pass


class TerminalSessionNotFoundError(LookupError):
    pass


class TerminalSessionClosedError(RuntimeError):
    pass


class TerminalProcess(Protocol):
    exitstatus: Optional[int]

    def read(self, size: int = 4096) -> str | bytes: ...
    def write(self, data: str) -> Any: ...
    def isalive(self) -> bool: ...
    def setwinsize(self, rows: int, cols: int) -> Any: ...
    def close(self, force: bool = True) -> Any: ...


@dataclass
class _TerminalSession:
    session_id: str
    workspace: Path
    workspace_key: str
    shell: str
    shell_path: str
    process: TerminalProcess
    columns: int
    rows: int
    created_at: str
    last_activity_at: str
    status: str = "running"
    agent: Optional[str] = None
    exit_code: Optional[int] = None
    history: Deque[str] = field(default_factory=deque)
    history_characters: int = 0
    subscribers: set[asyncio.Queue[Dict[str, Any]]] = field(default_factory=set)
    stop_reader: threading.Event = field(default_factory=threading.Event)
    reader_thread: Optional[threading.Thread] = None
    io_lock: RLock = field(default_factory=RLock)


class TerminalService:
    def __init__(
        self,
        workspace_service: WorkspaceService,
        *,
        platform_name: Optional[str] = None,
        max_history_characters: int = 200_000,
        max_sessions: int = 4,
    ) -> None:
        self.workspace_service = workspace_service
        self.platform_name = platform_name or os.name
        self.max_history_characters = max_history_characters
        self.max_sessions = max_sessions

        self._sessions: Dict[str, _TerminalSession] = {}
        self._workspace_sessions: Dict[str, str] = {}
        self._lock = RLock()
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

    async def create_session(
        self,
        *,
        shell: str = "auto",
        columns: int = DEFAULT_COLUMNS,
        rows: int = DEFAULT_ROWS,
    ) -> Dict[str, Any]:
        columns, rows = self._validated_dimensions(columns, rows)
        workspace = self.workspace_service.get_workspace().resolve()
        workspace_key = os.path.normcase(str(workspace))
        loop = asyncio.get_running_loop()
        self._event_loop = loop

        with self._lock:
            existing_id = self._workspace_sessions.get(workspace_key)
            existing = self._sessions.get(existing_id) if existing_id else None

            if existing is not None and self._is_running(existing):
                return {"session": self._public(existing), "reused": True}

            if existing is not None:
                self._remove_session_locked(existing)

            running_count = sum(
                1 for item in self._sessions.values() if self._is_running(item)
            )
            if running_count >= self.max_sessions:
                raise RuntimeError(
                    f"At most {self.max_sessions} terminal sessions may run at once"
                )

        shell_name, shell_path = self._resolve_shell(shell)
        command_line = subprocess.list2cmdline(
            [
                shell_path,
                "-NoLogo",
                "-NoProfile",
                "-NoExit",
                "-Command",
                "$Host.UI.RawUI.WindowTitle='AI Lab Terminal'",
            ]
        )

        process = self._spawn_windows_process(
            command_line=command_line,
            cwd=str(workspace),
            env=self._terminal_environment(),
            dimensions=(rows, columns),
        )

        now = self._utc_now()
        session = _TerminalSession(
            session_id=uuid4().hex,
            workspace=workspace,
            workspace_key=workspace_key,
            shell=shell_name,
            shell_path=shell_path,
            process=process,
            columns=columns,
            rows=rows,
            created_at=now,
            last_activity_at=now,
        )

        with self._lock:
            self._sessions[session.session_id] = session
            self._workspace_sessions[workspace_key] = session.session_id

        reader = threading.Thread(
            target=self._reader_worker,
            args=(session.session_id, loop),
            name=f"ai-lab-terminal-{session.session_id[:8]}",
            daemon=True,
        )
        session.reader_thread = reader
        reader.start()

        return {"session": self._public(session), "reused": False}

    def diagnostics(self) -> Dict[str, Any]:
        claude_path = shutil.which("claude.cmd") or shutil.which("claude")
        return {
            "platform": os.name,
            "supported": self.platform_name == "nt",
            "pywinpty_installed": importlib.util.find_spec("winpty") is not None,
            "shells": {
                "pwsh": shutil.which("pwsh.exe") or shutil.which("pwsh"),
                "powershell": shutil.which("powershell.exe")
                or shutil.which("powershell"),
            },
            "claude": {
                "available": claude_path is not None,
                "path": claude_path,
            },
            "loopback_only": os.getenv(
                "TERMINAL_ALLOW_REMOTE", "false"
            ).strip().lower()
            not in {"1", "true", "yes", "on"},
        }

    def list_sessions(self) -> Dict[str, Any]:
        with self._lock:
            sessions = [self._public(item) for item in self._sessions.values()]
        sessions.sort(key=lambda item: item["created_at"], reverse=True)
        return {"sessions": sessions}

    def get_session(self, session_id: str) -> Dict[str, Any]:
        return self._public(self._require_session(session_id))

    def subscribe(
        self,
        session_id: str,
    ) -> tuple[asyncio.Queue[Dict[str, Any]], Dict[str, Any]]:
        session = self._require_session(session_id)
        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=512)

        with self._lock:
            session.subscribers.add(queue)
            snapshot = {
                "session": self._public(session),
                "output": "".join(session.history),
            }

        return queue, snapshot

    def unsubscribe(
        self,
        session_id: str,
        queue: asyncio.Queue[Dict[str, Any]],
    ) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is not None:
                session.subscribers.discard(queue)

    async def write(self, session_id: str, data: str) -> Dict[str, Any]:
        if not isinstance(data, str):
            raise TypeError("Terminal input must be text")
        if not data:
            return self.get_session(session_id)
        if len(data) > MAX_INPUT_CHARACTERS:
            raise ValueError(
                f"Terminal input may not exceed {MAX_INPUT_CHARACTERS} characters"
            )

        session = self._require_running_session(session_id)
        await asyncio.to_thread(self._write_process, session, data)

        with self._lock:
            session.last_activity_at = self._utc_now()

        return self._public(session)

    async def resize(
        self,
        session_id: str,
        *,
        columns: int,
        rows: int,
    ) -> Dict[str, Any]:
        columns, rows = self._validated_dimensions(columns, rows)
        session = self._require_running_session(session_id)

        await asyncio.to_thread(
            self._resize_process,
            session,
            rows,
            columns,
        )

        with self._lock:
            session.columns = columns
            session.rows = rows
            session.last_activity_at = self._utc_now()

        return self._public(session)

    async def interrupt(self, session_id: str) -> Dict[str, Any]:
        session = self._require_running_session(session_id)
        await asyncio.to_thread(self._write_process, session, "\x03")

        with self._lock:
            session.agent = None
            session.last_activity_at = self._utc_now()

        return self._public(session)

    async def launch_claude(
        self,
        session_id: str,
        *,
        mode: str = "new",
        resume_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        session = self._require_running_session(session_id)

        claude_path = shutil.which("claude.cmd") or shutil.which("claude")
        if claude_path is None:
            raise TerminalUnavailableError(
                "Claude Code is not installed. Install it from the terminal page."
            )

        arguments = self._claude_arguments(mode=mode, resume_id=resume_id)
        escaped_path = claude_path.replace("'", "''")
        command = f"& '{escaped_path}'"
        if arguments:
            command += f" {arguments}"

        await asyncio.to_thread(
            self._write_process,
            session,
            command + "\r",
        )

        with self._lock:
            session.agent = "claude-code"
            session.last_activity_at = self._utc_now()

        return {
            "session": self._public(session),
            "command": command,
        }

    async def install_claude(self, session_id: str) -> Dict[str, Any]:
        session = self._require_running_session(session_id)
        npm_path = shutil.which("npm.cmd") or shutil.which("npm")

        if npm_path is None:
            raise TerminalUnavailableError(
                "npm was not found. Install Node.js before installing Claude Code."
            )

        escaped_path = npm_path.replace("'", "''")
        command = (
            f"& '{escaped_path}' install -g "
            "@anthropic-ai/claude-code"
        )

        await asyncio.to_thread(
            self._write_process,
            session,
            command + "\r",
        )

        with self._lock:
            session.agent = "claude-installer"
            session.last_activity_at = self._utc_now()

        return {
            "session": self._public(session),
            "command": command,
        }

    async def close_session(self, session_id: str) -> Dict[str, Any]:
        session = self._require_session(session_id)

        with self._lock:
            session.status = "closing"
            session.stop_reader.set()

        await asyncio.to_thread(self._close_process, session)

        with self._lock:
            session.status = "closed"
            session.agent = None
            session.last_activity_at = self._utc_now()
            public = self._public(session)
            self._publish_locked(
                session,
                {
                    "type": "session_closed",
                    "session": public,
                },
            )
            self._remove_session_locked(session)

        return public

    def close_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())

        for session in sessions:
            session.stop_reader.set()
            self._close_process(session)

        with self._lock:
            self._sessions.clear()
            self._workspace_sessions.clear()

    def _reader_worker(
        self,
        session_id: str,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        with self._lock:
            session = self._sessions.get(session_id)

        if session is None:
            return

        terminal_error: Optional[str] = None

        while not session.stop_reader.is_set():
            try:
                # pywinpty's documented high-level API uses read() without a
                # requested byte count. It blocks until output is available and
                # then returns the available console data.
                output = session.process.read()
            except EOFError:
                break
            except Exception as error:
                if not session.stop_reader.is_set():
                    terminal_error = f"{type(error).__name__}: {error}"
                break

            text = self._decode_output(output)

            if text:
                try:
                    loop.call_soon_threadsafe(
                        self._record_output,
                        session_id,
                        text,
                    )
                except RuntimeError:
                    break
                continue

            try:
                if not session.process.isalive():
                    break
            except Exception:
                break

            time.sleep(0.01)

        exit_code = getattr(session.process, "exitstatus", None)

        try:
            loop.call_soon_threadsafe(
                self._mark_exited,
                session_id,
                exit_code,
                terminal_error,
            )
        except RuntimeError:
            pass

    def _record_output(self, session_id: str, text: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return

            session.history.append(text)
            session.history_characters += len(text)
            session.last_activity_at = self._utc_now()
            self._trim_history_locked(session)

            self._publish_locked(
                session,
                {
                    "type": "output",
                    "data": text,
                },
            )

    def _mark_exited(
        self,
        session_id: str,
        exit_code: Optional[int],
        error: Optional[str],
    ) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.status == "closed":
                return

            session.status = "error" if error else "exited"
            session.agent = None
            session.exit_code = exit_code
            session.last_activity_at = self._utc_now()

            event: Dict[str, Any] = {
                "type": "session_exited",
                "session": self._public(session),
            }

            if error:
                event["error"] = error

            self._publish_locked(session, event)

    def _publish_locked(
        self,
        session: _TerminalSession,
        event: Dict[str, Any],
    ) -> None:
        for queue in tuple(session.subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass

            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def _trim_history_locked(self, session: _TerminalSession) -> None:
        overflow = session.history_characters - self.max_history_characters

        while overflow > 0 and session.history:
            oldest = session.history[0]

            if len(oldest) <= overflow:
                session.history.popleft()
                session.history_characters -= len(oldest)
                overflow -= len(oldest)
                continue

            session.history[0] = oldest[overflow:]
            session.history_characters -= overflow
            overflow = 0

    def _require_session(self, session_id: str) -> _TerminalSession:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be a non-empty string")

        with self._lock:
            session = self._sessions.get(session_id.strip())

        if session is None:
            raise TerminalSessionNotFoundError(
                f"Terminal session was not found: {session_id}"
            )

        return session

    def _require_running_session(self, session_id: str) -> _TerminalSession:
        session = self._require_session(session_id)

        if not self._is_running(session):
            raise TerminalSessionClosedError(
                f"Terminal session is not running: {session_id}"
            )

        return session

    @staticmethod
    def _public(session: _TerminalSession) -> Dict[str, Any]:
        return {
            "session_id": session.session_id,
            "workspace": str(session.workspace),
            "shell": session.shell,
            "shell_path": session.shell_path,
            "status": session.status,
            "agent": session.agent,
            "columns": session.columns,
            "rows": session.rows,
            "created_at": session.created_at,
            "last_activity_at": session.last_activity_at,
            "exit_code": session.exit_code,
        }

    @staticmethod
    def _is_running(session: _TerminalSession) -> bool:
        if session.status != "running":
            return False

        try:
            return bool(session.process.isalive())
        except Exception:
            return False

    def _resolve_shell(self, requested: str) -> tuple[str, str]:
        if self.platform_name != "nt":
            raise TerminalUnavailableError(
                "The embedded terminal currently requires Windows"
            )

        normalized = requested.strip().lower()
        if normalized not in {"auto", "pwsh", "powershell"}:
            raise ValueError("shell must be auto, pwsh, or powershell")

        candidates = (
            ("pwsh", "pwsh.exe"),
            ("powershell", "powershell.exe"),
        )

        if normalized != "auto":
            candidates = tuple(
                item for item in candidates if item[0] == normalized
            )

        for shell_name, executable in candidates:
            path = shutil.which(executable)
            if path:
                return shell_name, path

        raise TerminalUnavailableError(
            "PowerShell was not found. Install PowerShell 7 or enable Windows PowerShell."
        )

    @staticmethod
    def _terminal_environment() -> Dict[str, str]:
        environment = os.environ.copy()
        environment.setdefault("TERM", "xterm-256color")
        environment.setdefault("COLORTERM", "truecolor")
        environment.setdefault("PYTHONIOENCODING", "utf-8")
        return environment

    @staticmethod
    def _claude_arguments(
        *,
        mode: str,
        resume_id: Optional[str],
    ) -> str:
        normalized = mode.strip().lower()

        if normalized == "new":
            return ""

        if normalized == "continue":
            return "--continue"

        if normalized != "resume":
            raise ValueError("mode must be new, continue, or resume")

        if resume_id is None or not resume_id.strip():
            return "--resume"

        clean_resume_id = resume_id.strip()

        if len(clean_resume_id) > MAX_RESUME_ID_CHARACTERS:
            raise ValueError(
                f"resume_id may not exceed {MAX_RESUME_ID_CHARACTERS} characters"
            )

        if not RESUME_ID_PATTERN.fullmatch(clean_resume_id):
            raise ValueError("resume_id contains unsupported characters")

        return f'--resume "{clean_resume_id}"'

    @staticmethod
    def _validated_dimensions(
        columns: int,
        rows: int,
    ) -> tuple[int, int]:
        if isinstance(columns, bool) or not isinstance(columns, int):
            raise TypeError("columns must be an integer")
        if isinstance(rows, bool) or not isinstance(rows, int):
            raise TypeError("rows must be an integer")
        if not MIN_COLUMNS <= columns <= MAX_COLUMNS:
            raise ValueError(
                f"columns must be between {MIN_COLUMNS} and {MAX_COLUMNS}"
            )
        if not MIN_ROWS <= rows <= MAX_ROWS:
            raise ValueError(
                f"rows must be between {MIN_ROWS} and {MAX_ROWS}"
            )

        return columns, rows

    @staticmethod
    def _write_process(
        session: _TerminalSession,
        data: str,
    ) -> None:
        with session.io_lock:
            session.process.write(data)

    @staticmethod
    def _resize_process(
        session: _TerminalSession,
        rows: int,
        columns: int,
    ) -> None:
        with session.io_lock:
            session.process.setwinsize(rows, columns)

    @staticmethod
    def _close_process(session: _TerminalSession) -> None:
        try:
            with session.io_lock:
                session.process.close(force=True)
        except Exception:
            pass

    @staticmethod
    def _decode_output(output: str | bytes | Any) -> str:
        if isinstance(output, bytes):
            return output.decode("utf-8", errors="replace")
        if output is None:
            return ""
        return str(output)

    @staticmethod
    def _spawn_windows_process(
        *,
        command_line: str,
        cwd: str,
        env: Dict[str, str],
        dimensions: tuple[int, int],
    ) -> TerminalProcess:
        try:
            from winpty import PtyProcess
        except ImportError as error:
            raise TerminalUnavailableError(
                "pywinpty is not installed. Run pip install -r requirements.txt."
            ) from error

        return PtyProcess.spawn(
            command_line,
            cwd=cwd,
            env=env,
            dimensions=dimensions,
        )

    def _remove_session_locked(self, session: _TerminalSession) -> None:
        self._sessions.pop(session.session_id, None)

        if self._workspace_sessions.get(session.workspace_key) == session.session_id:
            self._workspace_sessions.pop(session.workspace_key, None)

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
