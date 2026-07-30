import asyncio
import os
import queue
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.terminal_service import (
    TerminalService,
    TerminalSessionClosedError,
)


class TemporaryWorkspaceService:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def get_workspace(self) -> Path:
        return self.root


class FakeTerminalProcess:
    def __init__(self):
        self.exitstatus = None
        self.alive = True
        self.writes = []
        self.resizes = []
        self.closed = False
        self._output = queue.Queue()

    def read(self, size=4096):
        del size
        if not self.alive:
            raise EOFError()
        try:
            return self._output.get(timeout=0.05)
        except queue.Empty:
            return ""

    def emit(self, data):
        self._output.put(data)

    def write(self, data):
        self.writes.append(data)

    def isalive(self):
        return self.alive

    def setwinsize(self, rows, cols):
        self.resizes.append((rows, cols))

    def close(self, force=True):
        self.closed = force
        self.alive = False
        self.exitstatus = 0


class FakeProcessFactory:
    def __init__(self):
        self.calls = []
        self.processes = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        process = FakeTerminalProcess()
        self.processes.append(process)
        return process


class TerminalServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.factory = FakeProcessFactory()
        self.service = TerminalService(
            TemporaryWorkspaceService(self.root),
            process_factory=self.factory,
            platform_name="nt",
            max_history_characters=10_000,
            max_sessions=2,
        )
        self.which_patch = patch.object(
            shutil,
            "which",
            side_effect=lambda name: (
                r"C:\Program Files\PowerShell\7\pwsh.exe"
                if name == "pwsh.exe"
                else r"C:\Users\test\AppData\Roaming\npm\claude.cmd"
                if name in {"claude", "claude.cmd"}
                else None
            ),
        )
        self.which_patch.start()

    async def asyncTearDown(self):
        self.service.close_all()
        self.which_patch.stop()
        self.temp_dir.cleanup()

    async def test_session_starts_in_selected_workspace(self):
        created = await self.service.create_session(columns=100, rows=30)

        session = created["session"]
        call = self.factory.calls[0]
        self.assertFalse(created["reused"])
        self.assertEqual(session["workspace"], str(self.root.resolve()))
        self.assertEqual(call["cwd"], str(self.root.resolve()))
        self.assertEqual(call["dimensions"], (30, 100))
        self.assertIn("pwsh.exe", call["command_line"])

    async def test_running_workspace_session_is_reused(self):
        first = await self.service.create_session()
        second = await self.service.create_session()

        self.assertEqual(
            first["session"]["session_id"],
            second["session"]["session_id"],
        )
        self.assertTrue(second["reused"])
        self.assertEqual(len(self.factory.calls), 1)

    async def test_input_resize_interrupt_and_claude_commands_reach_pty(self):
        created = await self.service.create_session()
        session_id = created["session"]["session_id"]
        process = self.factory.processes[0]

        await self.service.write(session_id, "Get-Location\r")
        await self.service.resize(session_id, columns=140, rows=45)
        launched = await self.service.launch_claude(session_id, mode="continue")
        await self.service.interrupt(session_id)

        self.assertEqual(process.writes[0], "Get-Location\r")
        self.assertEqual(process.resizes[-1], (45, 140))
        self.assertIn("claude --continue\r", process.writes)
        self.assertEqual(process.writes[-1], "\x03")
        self.assertEqual(launched["command"], "claude --continue")

    async def test_reader_broadcasts_output_and_keeps_snapshot_history(self):
        created = await self.service.create_session()
        session_id = created["session"]["session_id"]
        process = self.factory.processes[0]
        queue_one, initial = self.service.subscribe(session_id)

        self.assertEqual(initial["output"], "")
        process.emit("PowerShell ready\r\n")
        event = await asyncio.wait_for(queue_one.get(), timeout=1)

        self.assertEqual(event, {"type": "output", "data": "PowerShell ready\r\n"})
        queue_two, snapshot = self.service.subscribe(session_id)
        self.assertIn("PowerShell ready", snapshot["output"])
        self.service.unsubscribe(session_id, queue_one)
        self.service.unsubscribe(session_id, queue_two)

    async def test_close_removes_session_and_closes_process(self):
        created = await self.service.create_session()
        session_id = created["session"]["session_id"]
        process = self.factory.processes[0]

        closed = await self.service.close_session(session_id)

        self.assertEqual(closed["status"], "closed")
        self.assertTrue(process.closed)
        self.assertEqual(self.service.list_sessions()["sessions"], [])

    async def test_dead_session_rejects_input(self):
        created = await self.service.create_session()
        session_id = created["session"]["session_id"]
        self.factory.processes[0].alive = False

        with self.assertRaises(TerminalSessionClosedError):
            await self.service.write(session_id, "dir\r")

    def test_resume_id_rejects_shell_injection(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            self.service._claude_command(
                mode="resume",
                resume_id="abc; Remove-Item -Recurse *",
            )

    def test_remote_terminal_defaults_to_disabled(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TERMINAL_ALLOW_REMOTE", None)
            self.assertTrue(self.service.diagnostics()["loopback_only"])


if __name__ == "__main__":
    unittest.main()
