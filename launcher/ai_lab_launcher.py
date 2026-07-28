from __future__ import annotations

import argparse
import hashlib
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
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import IO, Any

APP_VERSION = "1.0.0"
BACKEND_URL = "http://127.0.0.1:8000"
BACKEND_HEALTH_URL = f"{BACKEND_URL}/health"
FRONTEND_URL = "http://127.0.0.1:3000"
FRONTEND_HEALTH_URL = f"{FRONTEND_URL}/api/health"
OLLAMA_URL = "http://127.0.0.1:11434"
LOG_RETENTION_DAYS = 14

IDENTITY_ENV = {
    "checkout_id": "AI_LAB_CHECKOUT_ID",
    "source_fingerprint": "AI_LAB_SOURCE_FINGERPRINT",
}

SOURCE_DIRECTORIES = (
    "launcher",
    "backend/routes",
    "backend/services",
    "backend/tools",
    "backend/unity_docs",
    "frontend/app",
    "frontend/components",
    "frontend/features",
    "frontend/lib",
    "frontend/public",
)

SOURCE_FILES = (
    "backend/app.py",
    "backend/dependencies.py",
    "backend/main.py",
    "backend/requirements.txt",
    "frontend/eslint.config.mjs",
    "frontend/next.config.ts",
    "frontend/package-lock.json",
    "frontend/package.json",
    "frontend/postcss.config.mjs",
    "frontend/tsconfig.json",
    "start-ai-lab.ps1",
)


@dataclass
class ManagedProcess:
    name: str
    process: subprocess.Popen[str]
    log_file: IO[str]


@dataclass
class LaunchState:
    root: Path
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    processes: list[ManagedProcess] = field(default_factory=list)
    reused_services: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ServiceProbe:
    reachable: bool
    status: int | None
    payload: dict[str, Any] | None


class LaunchError(RuntimeError):
    pass


def request_ok(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 400
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def probe_json(url: str, timeout: float = 1.0) -> ServiceProbe:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            raw = response.read()
            payload = json.loads(raw.decode("utf-8")) if raw else None
            return ServiceProbe(
                reachable=True,
                status=response.status,
                payload=payload if isinstance(payload, dict) else None,
            )
    except urllib.error.HTTPError as error:
        return ServiceProbe(
            reachable=True,
            status=error.code,
            payload=None,
        )
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return ServiceProbe(reachable=False, status=None, payload=None)


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


def _source_paths(root: Path) -> list[Path]:
    paths: set[Path] = set()

    for relative in SOURCE_FILES:
        candidate = root / relative
        if candidate.is_file():
            paths.add(candidate)

    for relative in SOURCE_DIRECTORIES:
        directory = root / relative
        if not directory.is_dir():
            continue
        for candidate in directory.rglob("*"):
            if _is_runtime_source(root, candidate):
                paths.add(candidate)

    return sorted(paths, key=lambda item: item.relative_to(root).as_posix())


def _is_runtime_source(root: Path, path: Path) -> bool:
    if not path.is_file() or "__pycache__" in path.parts:
        return False

    relative = path.relative_to(root).as_posix()
    if relative.startswith("launcher/"):
        return path.suffix == ".py" and not path.name.startswith("test_")
    if relative.startswith("backend/unity_docs/"):
        return path.suffix.lower() == ".md"
    if relative.startswith("backend/"):
        return path.suffix == ".py"
    if relative.startswith("frontend/public/"):
        return True
    if relative.startswith("frontend/"):
        return path.suffix.lower() in {
            ".css",
            ".js",
            ".json",
            ".mjs",
            ".ts",
            ".tsx",
        }
    return False


def source_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for path in _source_paths(root):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def checkout_id(root: Path) -> str:
    resolved = str(root.resolve())
    normalized = resolved.casefold() if os.name == "nt" else resolved
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def runtime_identity(root: Path) -> dict[str, str]:
    return {
        "version": APP_VERSION,
        "checkout_id": checkout_id(root),
        "source_fingerprint": source_fingerprint(root),
    }


def identity_matches(
    probe: ServiceProbe,
    *,
    service: str,
    expected: dict[str, str],
) -> bool:
    payload = probe.payload or {}
    return (
        probe.reachable
        and probe.status is not None
        and 200 <= probe.status < 400
        and payload.get("status") == "ok"
        and payload.get("service") == service
        and payload.get("checkout_id") == expected["checkout_id"]
        and payload.get("source_fingerprint")
        == expected["source_fingerprint"]
    )


def wait_for_identity(
    url: str,
    *,
    service: str,
    expected: dict[str, str],
    timeout: float,
    process: subprocess.Popen[str] | None = None,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if identity_matches(
            probe_json(url),
            service=service,
            expected=expected,
        ):
            return True
        if process is not None and process.poll() is not None:
            return False
        time.sleep(0.35)
    return False


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


def build_marker_path(root: Path) -> Path:
    return root / "frontend" / ".next" / "ai-lab-build.json"


def read_build_marker(root: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(build_marker_path(root).read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def write_build_marker(root: Path) -> dict[str, Any]:
    if not (root / "frontend" / ".next" / "BUILD_ID").is_file():
        raise LaunchError(
            "No production frontend build exists. Run setup-ai-lab.ps1 -Build."
        )

    marker = {
        "service": "ai-lab-frontend",
        "version": APP_VERSION,
        "source_fingerprint": source_fingerprint(root),
        "built_at": datetime.now(timezone.utc).isoformat(),
    }
    path = build_marker_path(root)
    path.write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    return marker


def validate_installation(root: Path, mode: str) -> None:
    backend_python(root)
    npm_command()
    if not (root / "frontend" / "node_modules").is_dir():
        raise LaunchError("Frontend dependencies are missing. Run setup-ai-lab.ps1.")

    if mode != "production":
        return

    if not (root / "frontend" / ".next" / "BUILD_ID").is_file():
        raise LaunchError(
            "No production frontend build exists. Run setup-ai-lab.ps1 -Build."
        )

    marker = read_build_marker(root)
    expected_fingerprint = source_fingerprint(root)
    if marker is None:
        raise LaunchError(
            "The production build has no AI Lab source marker. "
            "Run setup-ai-lab.ps1 -Build."
        )
    if marker.get("source_fingerprint") != expected_fingerprint:
        raise LaunchError(
            "The production frontend build is stale for the current source. "
            "Run setup-ai-lab.ps1 -Build."
        )


def _process_flags() -> int:
    return subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0


def cleanup_old_logs(
    root: Path,
    *,
    retention_days: int = LOG_RETENTION_DAYS,
    now: datetime | None = None,
) -> list[Path]:
    log_directory = root / "backend" / "data" / "logs"
    if not log_directory.is_dir():
        return []

    reference = now or datetime.now(timezone.utc)
    cutoff = reference - timedelta(days=retention_days)
    removed: list[Path] = []

    for path in log_directory.glob("*.log"):
        try:
            modified = datetime.fromtimestamp(
                path.stat().st_mtime,
                tz=timezone.utc,
            )
            if modified < cutoff:
                path.unlink()
                removed.append(path)
        except OSError:
            continue

    return removed


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
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    log_file = (logs / f"{name}-{stamp}.log").open(
        "a", encoding="utf-8", buffering=1
    )
    log_file.write(
        "\n--- "
        f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} "
        "starting ---\n"
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


def _identity_environment(root: Path) -> dict[str, str]:
    identity = runtime_identity(root)
    return {
        IDENTITY_ENV["checkout_id"]: identity["checkout_id"],
        IDENTITY_ENV["source_fingerprint"]: identity["source_fingerprint"],
    }


def _raise_identity_conflict(name: str, url: str) -> None:
    raise LaunchError(
        f"{name} port is occupied by another app, checkout, or stale "
        f"AI Lab process ({url}). Stop that process explicitly and retry."
    )


def ensure_backend(state: LaunchState) -> None:
    expected = runtime_identity(state.root)
    existing = probe_json(BACKEND_HEALTH_URL)
    if existing.reachable:
        if not identity_matches(
            existing,
            service="ai-lab-backend",
            expected=expected,
        ):
            _raise_identity_conflict("FastAPI", BACKEND_HEALTH_URL)
        state.reused_services.append("backend")
        print("[ready] Matching FastAPI instance was already running")
        return

    environment = os.environ.copy()
    environment.update(
        {
            "HOST": "127.0.0.1",
            "PORT": "8000",
            **_identity_environment(state.root),
        }
    )
    managed = start_process(
        state,
        name="backend",
        command=[str(backend_python(state.root)), "app.py"],
        working_directory=state.root / "backend",
        environment=environment,
    )
    print("[start] FastAPI")
    if not wait_for_identity(
        BACKEND_HEALTH_URL,
        service="ai-lab-backend",
        expected=expected,
        timeout=45,
        process=managed.process,
    ):
        raise LaunchError(
            "FastAPI did not become ready with the expected source identity. "
            "See backend/data/logs/backend-*.log."
        )
    print("[ready] FastAPI")


def ensure_frontend(state: LaunchState, mode: str) -> None:
    expected = runtime_identity(state.root)
    existing = probe_json(FRONTEND_HEALTH_URL)
    if existing.reachable:
        if not identity_matches(
            existing,
            service="ai-lab-frontend",
            expected=expected,
        ):
            _raise_identity_conflict("Next.js", FRONTEND_HEALTH_URL)
        state.reused_services.append("frontend")
        print("[ready] Matching Next.js instance was already running")
        return

    script = "start" if mode == "production" else "dev"
    environment = os.environ.copy()
    environment.update(
        {
            "NEXT_PUBLIC_BACKEND_URL": BACKEND_URL,
            "NEXT_PUBLIC_API_BASE_URL": BACKEND_URL,
            **_identity_environment(state.root),
        }
    )
    managed = start_process(
        state,
        name="frontend",
        command=[
            npm_command(),
            "run",
            script,
            "--",
            "--hostname",
            "127.0.0.1",
        ],
        working_directory=state.root / "frontend",
        environment=environment,
    )
    print(f"[start] Next.js ({mode})")
    if not wait_for_identity(
        FRONTEND_HEALTH_URL,
        service="ai-lab-frontend",
        expected=expected,
        timeout=75,
        process=managed.process,
    ):
        raise LaunchError(
            "Next.js did not become ready with the expected source identity. "
            "See backend/data/logs/frontend-*.log."
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


def runtime_state_path(root: Path) -> Path:
    return root / "backend" / "data" / "launcher-state.json"


def write_runtime_state(
    state: LaunchState,
    mode: str,
    *,
    status: str,
    error: str | None = None,
) -> None:
    path = runtime_state_path(state.root)
    path.parent.mkdir(parents=True, exist_ok=True)
    identity = runtime_identity(state.root)
    path.write_text(
        json.dumps(
            {
                "status": status,
                "started_at": state.started_at,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "mode": mode,
                **identity,
                "owned_processes": [
                    {
                        "name": item.name,
                        "pid": item.process.pid,
                        "running": item.process.poll() is None,
                    }
                    for item in state.processes
                ],
                "reused_services": state.reused_services,
                "error": error,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _read_runtime_state(root: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(
            runtime_state_path(root).read_text(encoding="utf-8")
        )
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def status_report(root: Path) -> dict[str, Any]:
    identity = runtime_identity(root)
    backend = probe_json(BACKEND_HEALTH_URL)
    frontend = probe_json(FRONTEND_HEALTH_URL)
    marker = read_build_marker(root)
    backend_match = identity_matches(
        backend,
        service="ai-lab-backend",
        expected=identity,
    )
    frontend_match = identity_matches(
        frontend,
        service="ai-lab-frontend",
        expected=identity,
    )
    launcher_state = _read_runtime_state(root)
    if launcher_state is not None:
        recorded_status = launcher_state.get("status")
        launcher_state["effective_status"] = (
            "stale"
            if recorded_status in {"starting", "running"}
            and not backend_match
            and not frontend_match
            else recorded_status
        )

    return {
        "application": "AI Lab",
        "identity": identity,
        "services": {
            "backend": {
                "reachable": backend.reachable,
                "status": backend.status,
                "identity_match": backend_match,
            },
            "frontend": {
                "reachable": frontend.reachable,
                "status": frontend.status,
                "identity_match": frontend_match,
            },
            "ollama": {
                "reachable": request_ok(
                    f"{OLLAMA_URL}/api/tags",
                    timeout=2,
                )
            },
        },
        "production_build": {
            "present": (
                root / "frontend" / ".next" / "BUILD_ID"
            ).is_file(),
            "marker_present": marker is not None,
            "source_match": (
                marker is not None
                and marker.get("source_fingerprint")
                == identity["source_fingerprint"]
            ),
        },
        "launcher_state": launcher_state,
    }


def _command_version(command: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
            creationflags=(
                subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            ),
        )
        output = (completed.stdout or completed.stderr).strip()
        return output.splitlines()[0] if output else None
    except (OSError, subprocess.SubprocessError):
        return None


def _log_metadata(root: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    directory = root / "backend" / "data" / "logs"
    if not directory.is_dir():
        return result
    for path in sorted(directory.glob("*.log")):
        try:
            stat = path.stat()
            result.append(
                {
                    "name": path.name,
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(
                        stat.st_mtime,
                        tz=timezone.utc,
                    ).isoformat(),
                }
            )
        except OSError:
            continue
    return result


def create_diagnostics_bundle(root: Path) -> Path:
    directory = root / "backend" / "data" / "diagnostics"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = directory / f"AI-Lab-Diagnostics-{stamp}.zip"

    report = status_report(root)
    report["environment"] = {
        "python": sys.version.split()[0],
        "node": _command_version(["node", "--version"]),
        "npm": _command_version([npm_command(), "--version"]),
        "ollama": _command_version(["ollama", "--version"]),
        "platform": sys.platform,
    }
    report["installation"] = {
        "backend_environment": any(
            candidate.is_file()
            for candidate in (
                root / "backend" / ".venv" / "Scripts" / "python.exe",
                root / "backend" / ".venv" / "bin" / "python",
            )
        ),
        "frontend_dependencies": (
            root / "frontend" / "node_modules"
        ).is_dir(),
    }
    report["logs"] = _log_metadata(root)

    readme = (
        "AI Lab diagnostics\n\n"
        "This bundle contains runtime identity, service reachability, version "
        "information, and log file metadata. It intentionally excludes source "
        "files, prompts, environment-variable values, credentials, databases, "
        "and log contents.\n"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "diagnostics.json",
            json.dumps(report, indent=2) + "\n",
        )
        archive.writestr("README.txt", readme)

    return path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the complete AI Lab app")
    parser.add_argument(
        "--mode", choices=("development", "production"), default="development"
    )
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--check", action="store_true", help="Validate only")
    parser.add_argument("--status", action="store_true", help="Report status")
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Create a safe local diagnostics ZIP",
    )
    parser.add_argument(
        "--write-build-marker",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--root", type=Path, help="Override project root")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    state: LaunchState | None = None
    final_status = "stopped"
    error_message: str | None = None
    exit_code = 0

    try:
        root = args.root.resolve() if args.root else find_project_root()

        if args.write_build_marker:
            marker = write_build_marker(root)
            print(
                "Recorded production source fingerprint "
                f"{marker['source_fingerprint'][:12]}."
            )
            return 0

        if args.status:
            print(json.dumps(status_report(root), indent=2))
            return 0

        if args.diagnostics:
            print(f"Created diagnostics bundle: {create_diagnostics_bundle(root)}")
            return 0

        validate_installation(root, args.mode)
        if args.check:
            identity = runtime_identity(root)
            print(
                f"AI Lab installation is valid: {root}\n"
                f"Source fingerprint: {identity['source_fingerprint']}"
            )
            return 0

        cleanup_old_logs(root)
        state = LaunchState(root=root)
        write_runtime_state(state, args.mode, status="starting")
        report_ollama()
        ensure_backend(state)
        ensure_frontend(state, args.mode)
        write_runtime_state(state, args.mode, status="running")

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
    except LaunchError as error:
        error_message = str(error)
        final_status = "error"
        exit_code = 1
        print(f"\nAI Lab could not start: {error}", file=sys.stderr)
    finally:
        if state is not None:
            stop_processes(state)
            write_runtime_state(
                state,
                args.mode,
                status=final_status,
                error=error_message,
            )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
