from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import IO


BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:3000"
OLLAMA_URL = "http://127.0.0.1:11434"


@dataclass
class ManagedProcess:
    name: str
    process: subprocess.Popen[str]
    log_file: IO[str]


@dataclass
class LaunchState:
    root: Path
    processes: list[ManagedProcess] = field(default_factory=list)
    reused_services: list[str] = field(default_factory=list)


class LaunchError(RuntimeError):
    pass


def request_ok(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 400
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def wait_for_url(
    url: str,
    *,
    timeout: float,
    process: subprocess.Popen[str] | None = None,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if request_ok(url):
            return True
        if process is not None and process.poll() is not None:
            return False
        time.sleep(0.35)
    return False


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__).resolve()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "backend" / "main.py").is_file() and (
            candidate / "frontend" / "package.json"
        ).is_file():
            return candidate
    raise LaunchError("Could not locate the AI Lab project root.")


def backend_python(root: Path) -> Path:
    candidates = (
        root / "backend" / ".venv" / "Scripts" / "python.exe",
        root / "backend" / ".venv" / "bin" / "python",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise LaunchError(
        "Backend virtual environment is missing. Run setup-ai-lab.ps1 first."
    )


def npm_command() -> str:
    executable = shutil.which("npm.cmd") or shutil.which("npm")
    if not executable:
        raise LaunchError("npm was not found. Install Node.js 20 or newer.")
    return executable


def validate_installation(root: Path, mode: str) -> None:
    backend_python(root)
    npm_command()
    if not (root / "frontend" / "node_modules").is_dir():
        raise LaunchError("Frontend dependencies are missing. Run setup-ai-lab.ps1.")
    if mode == "production" and not (
        root / "frontend" / ".next" / "BUILD_ID"
    ).is_file():
        raise LaunchError(
            "No production frontend build exists. Run setup-ai-lab.ps1 -Build."
        )


def _process_flags() -> int:
    return subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0


def start_process(
    state: LaunchState,
    *,
    name: str,
    command: list[str],
    working_directory: Path,
    environment: dict[str, str],
) -> ManagedProcess:
    logs = state.root / "backend" / "data" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    log_file = (logs / f"{name}-{stamp}.log").open(
        "a", encoding="utf-8", buffering=1
    )
    log_file.write(
        f"\n--- {datetime.now().isoformat(timespec='seconds')} starting ---\n"
    )
    process = subprocess.Popen(
        command,
        cwd=working_directory,
        env=environment,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=_process_flags(),
    )
    managed = ManagedProcess(name=name, process=process, log_file=log_file)
    state.processes.append(managed)
    return managed


def ensure_backend(state: LaunchState) -> None:
    if request_ok(f"{BACKEND_URL}/health"):
        state.reused_services.append("backend")
        print("[ready] FastAPI was already running")
        return
    environment = os.environ.copy()
    environment.update({"HOST": "127.0.0.1", "PORT": "8000"})
    managed = start_process(
        state,
        name="backend",
        command=[str(backend_python(state.root)), "app.py"],
        working_directory=state.root / "backend",
        environment=environment,
    )
    print("[start] FastAPI")
    if not wait_for_url(
        f"{BACKEND_URL}/health", timeout=45, process=managed.process
    ):
        raise LaunchError(
            "FastAPI did not become ready. See backend/data/logs/backend-*.log."
        )
    print("[ready] FastAPI")


def ensure_frontend(state: LaunchState, mode: str) -> None:
    if request_ok(FRONTEND_URL):
        state.reused_services.append("frontend")
        print("[ready] Next.js was already running")
        return
    script = "start" if mode == "production" else "dev"
    environment = os.environ.copy()
    environment["NEXT_PUBLIC_BACKEND_URL"] = BACKEND_URL
    managed = start_process(
        state,
        name="frontend",
        command=[npm_command(), "run", script],
        working_directory=state.root / "frontend",
        environment=environment,
    )
    print(f"[start] Next.js ({mode})")
    if not wait_for_url(FRONTEND_URL, timeout=75, process=managed.process):
        raise LaunchError(
            "Next.js did not become ready. See backend/data/logs/frontend-*.log."
        )
    print("[ready] Next.js")


def report_ollama() -> None:
    if request_ok(f"{OLLAMA_URL}/api/tags", timeout=2):
        print("[ready] Ollama")
    else:
        print(
            "[warning] Ollama is not reachable. AI Lab will open, but model "
            "requests will fail until Ollama is started."
        )


def stop_processes(state: LaunchState) -> None:
    for managed in reversed(state.processes):
        process = managed.process
        if process.poll() is not None:
            managed.log_file.close()
            continue
        print(f"[stop] {managed.name}")
        try:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.terminate()
            process.wait(timeout=8)
        except (subprocess.TimeoutExpired, OSError):
            process.kill()
            process.wait(timeout=5)
        finally:
            managed.log_file.close()


def write_runtime_state(state: LaunchState, mode: str) -> None:
    path = state.root / "backend" / "data" / "launcher-state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "started_at": datetime.now().isoformat(timespec="seconds"),
                "mode": mode,
                "owned_processes": [
                    {"name": item.name, "pid": item.process.pid}
                    for item in state.processes
                ],
                "reused_services": state.reused_services,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the complete AI Lab app")
    parser.add_argument(
        "--mode", choices=("development", "production"), default="development"
    )
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--check", action="store_true", help="Validate only")
    parser.add_argument("--root", type=Path, help="Override project root")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    state: LaunchState | None = None
    try:
        root = args.root.resolve() if args.root else find_project_root()
        validate_installation(root, args.mode)
        if args.check:
            print(f"AI Lab installation is valid: {root}")
            return 0
        state = LaunchState(root=root)
        report_ollama()
        ensure_backend(state)
        ensure_frontend(state, args.mode)
        write_runtime_state(state, args.mode)
        if not args.no_browser:
            webbrowser.open(FRONTEND_URL)
        print(f"\nAI Lab is ready at {FRONTEND_URL}")
        print("Press Ctrl+C to stop services started by this launcher.")
        while True:
            for managed in state.processes:
                if managed.process.poll() is not None:
                    raise LaunchError(f"{managed.name} stopped unexpectedly.")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down AI Lab…")
        return 0
    except LaunchError as error:
        print(f"\nAI Lab could not start: {error}", file=sys.stderr)
        return 1
    finally:
        if state is not None:
            stop_processes(state)


if __name__ == "__main__":
    raise SystemExit(main())
