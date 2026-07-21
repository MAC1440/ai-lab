from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import time
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any, AsyncIterator, Dict, List, Optional
from pathlib import Path
from uuid import uuid4

from services.project_detection_service import ProjectDetectionService
from services.verification_store import VerificationStore
from services.workspace_service import WorkspaceService


class VerificationBusyError(RuntimeError):
    """Raised when a workspace already has an active verification run."""


class VerificationUnavailableError(RuntimeError):
    """Raised when a detected profile cannot run on this machine."""


class VerificationRunNotActiveError(RuntimeError):
    """Raised when cancellation targets a run that is no longer active."""


@dataclass
class _ActiveRun:
    run_id: str
    workspace_key: str
    cancel_event: asyncio.Event
    process: Optional[asyncio.subprocess.Process] = None


class VerificationService:
    """Run allowlisted workspace checks and stream their lifecycle events."""

    def __init__(
        self,
        workspace_service: WorkspaceService,
        project_detection_service: ProjectDetectionService,
        store: VerificationStore,
        *,
        max_output_chars: int = 200_000,
    ) -> None:
        if max_output_chars < 10_000:
            raise ValueError("max_output_chars must be at least 10000")

        self.workspace_service = workspace_service
        self.project_detection_service = project_detection_service
        self.store = store
        self.max_output_chars = max_output_chars
        self._active_by_workspace: Dict[str, _ActiveRun] = {}
        self._active_by_run_id: Dict[str, _ActiveRun] = {}
        self._active_lock = RLock()

    async def run_events(
        self,
        *,
        profile_id: str,
        proposal_id: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        workspace = self.workspace_service.get_workspace().resolve()
        profile = self.project_detection_service.get_profile(profile_id)

        if not profile.available:
            raise VerificationUnavailableError(
                profile.unavailable_reason or "The verification profile is unavailable"
            )

        current_workspace = self.workspace_service.get_workspace().resolve()
        if current_workspace != workspace:
            raise RuntimeError(
                "The active workspace changed while verification was preparing"
            )

        working_directory = (workspace / profile.working_directory).resolve()
        try:
            working_directory.relative_to(workspace)
        except ValueError as error:
            raise PermissionError(
                "Verification working directory escaped the active workspace"
            ) from error

        if not working_directory.is_dir():
            raise NotADirectoryError(
                "Verification working directory no longer exists: "
                f"{profile.working_directory}"
            )

        run_id = uuid4().hex
        workspace_key = os.path.normcase(str(workspace))
        active_run = _ActiveRun(
            run_id=run_id,
            workspace_key=workspace_key,
            cancel_event=asyncio.Event(),
        )
        self._reserve(active_run)

        started_at = self._utc_now()
        started_clock = time.monotonic()
        output_parts: List[str] = []
        output_length = 0
        output_truncated = False
        process: Optional[asyncio.subprocess.Process] = None
        finalized = False
        stored = False

        try:
            self._prepare_result_file(profile.result_file)
            self.store.create_run(
                run_id=run_id,
                workspace=str(workspace),
                profile_id=profile.profile_id,
                profile_name=profile.name,
                project_type=profile.project_type,
                working_directory=profile.working_directory,
                command=list(profile.command),
                display_command=profile.display_command,
                proposal_id=proposal_id,
                started_at=started_at,
            )
            stored = True

            yield {
                "type": "verification_started",
                "run_id": run_id,
                "workspace": str(workspace),
                "profile": profile.public(),
                "proposal_id": proposal_id,
                "started_at": started_at,
            }

            process = await asyncio.create_subprocess_exec(
                *profile.command,
                cwd=working_directory,
                env=self._safe_environment(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                **self._process_group_options(),
            )
            active_run.process = process

            yield {
                "type": "command_started",
                "run_id": run_id,
                "command": profile.display_command,
                "working_directory": profile.working_directory,
            }

            deadline = started_clock + profile.timeout_seconds
            terminal_status: Optional[str] = None
            terminal_error: Optional[str] = None

            while True:
                if active_run.cancel_event.is_set():
                    terminal_status = "cancelled"
                    terminal_error = "Verification was cancelled by the user."
                    await self._stop_process(process)
                    break

                if time.monotonic() >= deadline:
                    terminal_status = "timed_out"
                    terminal_error = (
                        "Verification exceeded its "
                        f"{profile.timeout_seconds}-second timeout."
                    )
                    await self._stop_process(process)
                    break

                if process.stdout is None:
                    break

                try:
                    chunk = await asyncio.wait_for(
                        process.stdout.read(4096),
                        timeout=0.25,
                    )
                except asyncio.TimeoutError:
                    if process.returncode is not None:
                        break
                    continue

                if not chunk:
                    break

                text = chunk.decode("utf-8", errors="replace")
                remaining = self.max_output_chars - output_length

                if remaining > 0:
                    stored_text = text[:remaining]
                    output_parts.append(stored_text)
                    output_length += len(stored_text)

                if len(text) > remaining:
                    output_truncated = True

                yield {
                    "type": "output",
                    "run_id": run_id,
                    "stream": "stdout",
                    "content": text,
                }

            if process.returncode is None:
                await process.wait()

            exit_code = process.returncode
            if terminal_status is None:
                terminal_status = "passed" if exit_code == 0 else "failed"

            validation_output, validation_error = self._validate_profile_result(
                profile=profile,
                output="".join(output_parts),
            )
            if validation_output:
                remaining = self.max_output_chars - output_length
                if remaining > 0:
                    output_parts.append(validation_output[:remaining])
                    output_length += min(len(validation_output), remaining)
                if len(validation_output) > remaining:
                    output_truncated = True
                yield {
                    "type": "output",
                    "run_id": run_id,
                    "stream": "stdout",
                    "content": validation_output,
                }
            if terminal_status == "passed" and validation_error:
                terminal_status = "failed"
                terminal_error = validation_error

            duration_ms = self._duration_ms(started_clock)
            result = self.store.finish_run(
                run_id,
                status=terminal_status,
                finished_at=self._utc_now(),
                duration_ms=duration_ms,
                exit_code=exit_code,
                output="".join(output_parts),
                output_truncated=output_truncated,
                error=terminal_error,
            )
            finalized = True

            yield {
                "type": "command_finished",
                "run_id": run_id,
                "exit_code": exit_code,
                "duration_ms": duration_ms,
            }
            yield {
                "type": "verification_done",
                "result": result,
            }

        except asyncio.CancelledError:
            if process is not None:
                await self._stop_process(process)

            if stored and not finalized:
                self._finish_after_error(
                    run_id=run_id,
                    started_clock=started_clock,
                    process=process,
                    output="".join(output_parts),
                    output_truncated=output_truncated,
                    status="cancelled",
                    error="The verification stream was disconnected.",
                )
                finalized = True
            raise
        except Exception as error:
            if process is not None:
                await self._stop_process(process)

            if stored and not finalized:
                result = self._finish_after_error(
                    run_id=run_id,
                    started_clock=started_clock,
                    process=process,
                    output="".join(output_parts),
                    output_truncated=output_truncated,
                    status="error",
                    error=str(error),
                )
                finalized = True
                yield {
                    "type": "verification_done",
                    "result": result,
                }
            elif not stored:
                raise
        finally:
            if stored and not finalized:
                if process is not None:
                    await self._stop_process(process)
                try:
                    self._finish_after_error(
                        run_id=run_id,
                        started_clock=started_clock,
                        process=process,
                        output="".join(output_parts),
                        output_truncated=output_truncated,
                        status="cancelled",
                        error="The verification stream was closed before completion.",
                    )
                except Exception:
                    # The stream is already closing, so cleanup must not mask
                    # the original disconnect or generator-close exception.
                    pass
            self._release(active_run)
            self._cleanup_result_file(profile.result_file)

    def cancel(self, run_id: str) -> Dict[str, Any]:
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("run_id must be a non-empty string")

        with self._active_lock:
            active_run = self._active_by_run_id.get(run_id.strip())
            if active_run is None:
                raise VerificationRunNotActiveError(
                    f"Verification run is not active: {run_id}"
                )
            active_run.cancel_event.set()

        return {
            "run_id": active_run.run_id,
            "cancellation_requested": True,
        }

    @staticmethod
    def _prepare_result_file(result_file: Optional[str]) -> None:
        if not result_file:
            return
        path = Path(result_file)
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            raise RuntimeError(
                f"Could not prepare verification result file: {error}"
            ) from error

    @staticmethod
    def _cleanup_result_file(result_file: Optional[str]) -> None:
        if not result_file:
            return
        try:
            Path(result_file).unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def _validate_profile_result(
        *,
        profile,
        output: str,
    ) -> tuple[str, Optional[str]]:
        if profile.project_type != "unity":
            return "", None

        compiler_patterns = (
            r"\berror CS\d{4}\b",
            r"Scripts have compiler errors",
            r"Compilation failed",
            r"Aborting batchmode due to failure",
        )
        if any(
            re.search(pattern, output, flags=re.IGNORECASE)
            for pattern in compiler_patterns
        ):
            return "", "Unity reported compiler or batch-mode errors in its log."

        if profile.result_format != "nunit-xml" or not profile.result_file:
            return "", None

        result_path = Path(profile.result_file)
        if not result_path.is_file():
            return (
                "\n[AI Lab] Unity did not create the requested test-results XML.\n",
                "Unity EditMode tests did not produce a result file.",
            )
        try:
            root = ET.parse(result_path).getroot()
        except (OSError, ET.ParseError) as error:
            return (
                f"\n[AI Lab] Unity test results could not be parsed: {error}\n",
                "Unity produced an unreadable test-results file.",
            )

        def count(*names: str) -> int:
            for name in names:
                value = root.attrib.get(name)
                if value is not None:
                    try:
                        return int(value)
                    except ValueError:
                        return 0
            return 0

        total = count("total", "total-tests")
        failures = count("failed", "failures")
        errors = count("errors")
        skipped = count("skipped", "not-run", "inconclusive")
        result = root.attrib.get("result", "").lower()
        summary = (
            "\n[AI Lab] Unity EditMode results: "
            f"total={total}, failed={failures}, errors={errors}, "
            f"skipped={skipped}.\n"
        )
        failed = failures > 0 or errors > 0 or result in {"failed", "failure"}
        return (
            summary,
            "Unity EditMode tests reported failures."
            if failed
            else None,
        )

    def _reserve(self, active_run: _ActiveRun) -> None:
        with self._active_lock:
            existing = self._active_by_workspace.get(active_run.workspace_key)
            if existing is not None:
                raise VerificationBusyError(
                    "This workspace already has an active verification run"
                )

            self._active_by_workspace[active_run.workspace_key] = active_run
            self._active_by_run_id[active_run.run_id] = active_run

    def _release(self, active_run: _ActiveRun) -> None:
        with self._active_lock:
            current_workspace_run = self._active_by_workspace.get(
                active_run.workspace_key
            )
            if current_workspace_run is active_run:
                self._active_by_workspace.pop(active_run.workspace_key, None)

            current_id_run = self._active_by_run_id.get(active_run.run_id)
            if current_id_run is active_run:
                self._active_by_run_id.pop(active_run.run_id, None)

    def _finish_after_error(
        self,
        *,
        run_id: str,
        started_clock: float,
        process: Optional[asyncio.subprocess.Process],
        output: str,
        output_truncated: bool,
        status: str,
        error: str,
    ) -> Dict[str, Any]:
        return self.store.finish_run(
            run_id,
            status=status,
            finished_at=self._utc_now(),
            duration_ms=self._duration_ms(started_clock),
            exit_code=process.returncode if process is not None else None,
            output=output,
            output_truncated=output_truncated,
            error=error,
        )

    @staticmethod
    def _safe_environment() -> Dict[str, str]:
        allowed_names = {
            "ALLUSERSPROFILE",
            "APPDATA",
            "COMSPEC",
            "HOME",
            "HOMEDRIVE",
            "HOMEPATH",
            "LOCALAPPDATA",
            "NUMBER_OF_PROCESSORS",
            "OS",
            "PATH",
            "PATHEXT",
            "PROGRAMDATA",
            "PROGRAMFILES",
            "PROGRAMFILES(X86)",
            "PROGRAMW6432",
            "SYSTEMDRIVE",
            "SYSTEMROOT",
            "TEMP",
            "TMP",
            "USERPROFILE",
            "VIRTUAL_ENV",
            "WINDIR",
        }
        environment = {
            key: value
            for key, value in os.environ.items()
            if key.upper() in allowed_names
        }
        environment.update(
            {
                "CI": "1",
                "NO_COLOR": "1",
                "PYTHONUNBUFFERED": "1",
            }
        )
        return environment

    @staticmethod
    def _process_group_options() -> Dict[str, Any]:
        if os.name == "nt":
            return {
                "creationflags": getattr(
                    subprocess,
                    "CREATE_NEW_PROCESS_GROUP",
                    0x00000200,
                ),
            }

        return {"start_new_session": True}

    @staticmethod
    async def _stop_process(process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return

        if os.name == "nt":
            try:
                killer = await asyncio.create_subprocess_exec(
                    "taskkill",
                    "/PID",
                    str(process.pid),
                    "/T",
                    "/F",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await killer.wait()
            except (OSError, ProcessLookupError):
                process.terminate()
        else:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                return

        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            if os.name == "nt":
                process.kill()
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            await process.wait()

    @staticmethod
    def _duration_ms(started_clock: float) -> int:
        return max(0, round((time.monotonic() - started_clock) * 1000))

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
