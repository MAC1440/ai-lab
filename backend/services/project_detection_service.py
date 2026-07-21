from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from services.workspace_service import WorkspaceService


IGNORED_DIRECTORIES = {
    ".git",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "Library",
    "Logs",
    "Temp",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "obj",
    "venv",
}


@dataclass(frozen=True)
class VerificationProfile:
    profile_id: str
    name: str
    description: str
    project_type: str
    working_directory: str
    command: Tuple[str, ...]
    display_command: str
    timeout_seconds: int
    available: bool
    unavailable_reason: Optional[str] = None
    result_file: Optional[str] = None
    result_format: Optional[str] = None

    def public(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "description": self.description,
            "project_type": self.project_type,
            "working_directory": self.working_directory,
            "command": self.display_command,
            "timeout_seconds": self.timeout_seconds,
            "available": self.available,
            "unavailable_reason": self.unavailable_reason,
            "result_format": self.result_format,
        }


class ProjectDetectionService:
    """Detect project types and build safe, predefined verification profiles."""

    def __init__(
        self,
        workspace_service: WorkspaceService,
        *,
        max_scan_depth: int = 2,
    ) -> None:
        if max_scan_depth < 0 or max_scan_depth > 5:
            raise ValueError("max_scan_depth must be between 0 and 5")

        self.workspace_service = workspace_service
        self.max_scan_depth = max_scan_depth

    def inspect_workspace(self) -> Dict[str, Any]:
        workspace = self.workspace_service.get_workspace().resolve()
        projects, profiles = self._detect(workspace)

        return {
            "workspace": str(workspace),
            "projects": projects,
            "profiles": [profile.public() for profile in profiles],
        }

    def get_profile(self, profile_id: str) -> VerificationProfile:
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("profile_id must be a non-empty string")

        workspace = self.workspace_service.get_workspace().resolve()
        _, profiles = self._detect(workspace)

        for profile in profiles:
            if profile.profile_id == profile_id.strip():
                return profile

        raise LookupError(
            "Verification profile is not available for the active workspace: "
            f"{profile_id}"
        )

    def _detect(
        self,
        workspace: Path,
    ) -> Tuple[List[Dict[str, Any]], List[VerificationProfile]]:
        projects: List[Dict[str, Any]] = []
        profiles: List[VerificationProfile] = []

        for directory in self._candidate_directories(workspace):
            relative = self._relative_text(workspace, directory)

            python_project = self._detect_python(directory, relative)
            if python_project is not None:
                project, detected_profiles = python_project
                projects.append(project)
                profiles.extend(detected_profiles)

            node_project = self._detect_node(directory, relative)
            if node_project is not None:
                project, detected_profiles = node_project
                projects.append(project)
                profiles.extend(detected_profiles)

            dotnet_project = self._detect_dotnet(directory, relative)
            if dotnet_project is not None:
                project, detected_profiles = dotnet_project
                projects.append(project)
                profiles.extend(detected_profiles)

            unity_project = self._detect_unity(directory, relative)
            if unity_project is not None:
                project, detected_profiles = unity_project
                projects.append(project)
                profiles.extend(detected_profiles)

        projects.sort(key=lambda item: (item["root"], item["type"]))
        profiles.sort(
            key=lambda profile: (
                profile.working_directory,
                profile.project_type,
                profile.name,
            )
        )
        return projects, profiles

    def _candidate_directories(self, workspace: Path) -> Iterable[Path]:
        stack: List[Tuple[Path, int]] = [(workspace, 0)]

        while stack:
            directory, depth = stack.pop()
            yield directory

            if depth >= self.max_scan_depth:
                continue

            try:
                children = sorted(
                    (
                        child
                        for child in directory.iterdir()
                        if child.is_dir()
                        and child.name not in IGNORED_DIRECTORIES
                        and not child.is_symlink()
                    ),
                    key=lambda child: child.name.lower(),
                    reverse=True,
                )
            except (OSError, PermissionError):
                continue

            for child in children:
                stack.append((child, depth + 1))

    def _detect_python(
        self,
        directory: Path,
        relative: str,
    ) -> Optional[Tuple[Dict[str, Any], List[VerificationProfile]]]:
        markers = self._existing_names(
            directory,
            (
                "pyproject.toml",
                "pytest.ini",
                "requirements.txt",
                "requirements-dev.txt",
                "setup.cfg",
                "setup.py",
                "tox.ini",
            ),
        )

        if not markers:
            return None

        profiles: List[VerificationProfile] = []
        has_tests = (directory / "tests").is_dir() or any(
            marker in markers for marker in ("pytest.ini", "pyproject.toml", "tox.ini")
        )

        if has_tests:
            pytest_available = importlib.util.find_spec("pytest") is not None
            profiles.append(
                self._profile(
                    action="pytest",
                    name=f"Python tests ({relative})",
                    description="Run the Python test suite with pytest.",
                    project_type="python",
                    working_directory=relative,
                    command=(
                        sys.executable,
                        "-m",
                        "pytest",
                        "-q",
                        "--tb=short",
                    ),
                    display_command="python -m pytest -q --tb=short",
                    timeout_seconds=300,
                    available=pytest_available,
                    unavailable_reason=(
                        None
                        if pytest_available
                        else "pytest is not installed in the backend environment"
                    ),
                )
            )

        if self._python_dependency_is_declared(directory, "ruff"):
            ruff_module_available = importlib.util.find_spec("ruff") is not None
            ruff_executable = shutil.which("ruff")
            ruff_available = ruff_module_available or ruff_executable is not None
            ruff_command = (
                (sys.executable, "-m", "ruff", "check", ".")
                if ruff_module_available
                else (ruff_executable or "ruff", "check", ".")
            )
            profiles.append(
                self._profile(
                    action="ruff",
                    name=f"Python lint ({relative})",
                    description="Check Python formatting and common errors with Ruff.",
                    project_type="python",
                    working_directory=relative,
                    command=ruff_command,
                    display_command="python -m ruff check .",
                    timeout_seconds=180,
                    available=ruff_available,
                    unavailable_reason=(
                        None
                        if ruff_available
                        else "ruff is declared but is not installed"
                    ),
                )
            )

        return (
            {
                "type": "python",
                "name": "Python",
                "root": relative,
                "markers": markers,
            },
            profiles,
        )

    def _detect_node(
        self,
        directory: Path,
        relative: str,
    ) -> Optional[Tuple[Dict[str, Any], List[VerificationProfile]]]:
        package_json = directory / "package.json"
        if not package_json.is_file():
            return None

        try:
            package_data = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return (
                {
                    "type": "node",
                    "name": "Node.js",
                    "root": relative,
                    "markers": ["package.json"],
                    "warning": "package.json could not be parsed",
                },
                [],
            )

        raw_scripts = package_data.get("scripts", {})
        scripts = raw_scripts if isinstance(raw_scripts, dict) else {}
        npm_command_prefix = self._npm_command_prefix()
        profiles: List[VerificationProfile] = []

        script_settings = {
            "test": ("Tests", 300),
            "lint": ("Lint", 180),
            "typecheck": ("Type check", 300),
            "build": ("Production build", 600),
        }

        for script_name, (label, timeout_seconds) in script_settings.items():
            if not isinstance(scripts.get(script_name), str):
                continue

            profiles.append(
                self._profile(
                    action=f"npm-{script_name}",
                    name=f"{label} ({relative})",
                    description=f"Run the package.json {script_name} script.",
                    project_type="node",
                    working_directory=relative,
                    command=(
                        (*npm_command_prefix, "run", script_name)
                        if npm_command_prefix
                        else ("npm", "run", script_name)
                    ),
                    display_command=f"npm run {script_name}",
                    timeout_seconds=timeout_seconds,
                    available=npm_command_prefix is not None,
                    unavailable_reason=(
                        None if npm_command_prefix else "npm was not found on PATH"
                    ),
                )
            )

        return (
            {
                "type": "node",
                "name": "Node.js",
                "root": relative,
                "markers": ["package.json"],
            },
            profiles,
        )

    def _detect_dotnet(
        self,
        directory: Path,
        relative: str,
    ) -> Optional[Tuple[Dict[str, Any], List[VerificationProfile]]]:
        try:
            solution_files = sorted(path.name for path in directory.glob("*.sln"))
            project_files = sorted(path.name for path in directory.glob("*.csproj"))
        except OSError:
            return None

        markers = solution_files + project_files
        if not markers:
            return None

        dotnet_path = shutil.which("dotnet")
        profile = self._profile(
            action="dotnet-test",
            name=f".NET tests ({relative})",
            description="Build and run tests with the .NET SDK.",
            project_type="dotnet",
            working_directory=relative,
            command=(dotnet_path or "dotnet", "test", "--nologo"),
            display_command="dotnet test --nologo",
            timeout_seconds=600,
            available=dotnet_path is not None,
            unavailable_reason=(
                None if dotnet_path else "dotnet was not found on PATH"
            ),
        )

        return (
            {
                "type": "dotnet",
                "name": ".NET",
                "root": relative,
                "markers": markers,
            },
            [profile],
        )

    def _detect_unity(
        self,
        directory: Path,
        relative: str,
    ) -> Optional[Tuple[Dict[str, Any], List[VerificationProfile]]]:
        project_version = directory / "ProjectSettings" / "ProjectVersion.txt"
        assets = directory / "Assets"

        if not project_version.is_file() or not assets.is_dir():
            return None

        version = self._read_unity_version(project_version)
        editor_setting = os.getenv("UNITY_EDITOR_PATH", "").strip()
        editor_path = Path(editor_setting).expanduser() if editor_setting else None
        editor_available = bool(editor_path and editor_path.is_file())
        command_editor = str(editor_path) if editor_path else "Unity"

        compile_profile = self._profile(
            action="unity-compile",
            name=f"Unity compile check ({relative})",
            description=(
                "Open the project in Unity batch mode and capture compiler output. "
                "Close the Unity Editor before running this check."
            ),
            project_type="unity",
            working_directory=relative,
            command=(
                command_editor,
                "-batchmode",
                "-nographics",
                "-quit",
                "-projectPath",
                ".",
                "-logFile",
                "-",
            ),
            display_command=(
                "Unity -batchmode -nographics -quit -projectPath . -logFile -"
            ),
            timeout_seconds=900,
            available=editor_available,
            unavailable_reason=(
                None
                if editor_available
                else "Set UNITY_EDITOR_PATH to the full Unity executable path"
            ),
        )

        project: Dict[str, Any] = {
            "type": "unity",
            "name": "Unity",
            "root": relative,
            "markers": ["Assets", "ProjectSettings/ProjectVersion.txt"],
        }
        if version:
            project["version"] = version

        profiles = [compile_profile]
        if self._unity_test_framework_declared(directory):
            result_identity = hashlib.sha256(
                str(directory.resolve()).encode("utf-8")
            ).hexdigest()[:16]
            result_file = str(
                Path(tempfile.gettempdir())
                / f"ai-lab-unity-editmode-{result_identity}.xml"
            )
            profiles.append(
                self._profile(
                    action="unity-editmode-tests",
                    name=f"Unity EditMode tests ({relative})",
                    description=(
                        "Run Unity Test Framework EditMode tests in batch mode "
                        "and validate the generated NUnit XML. Close the Unity "
                        "Editor before running this check."
                    ),
                    project_type="unity",
                    working_directory=relative,
                    command=(
                        command_editor,
                        "-batchmode",
                        "-nographics",
                        "-runTests",
                        "-testPlatform",
                        "EditMode",
                        "-projectPath",
                        ".",
                        "-testResults",
                        result_file,
                        "-logFile",
                        "-",
                    ),
                    display_command=(
                        "Unity -batchmode -nographics -runTests "
                        "-testPlatform EditMode -projectPath . "
                        "-testResults <temporary-results.xml> -logFile -"
                    ),
                    timeout_seconds=1200,
                    available=editor_available,
                    unavailable_reason=(
                        None
                        if editor_available
                        else "Set UNITY_EDITOR_PATH to the full Unity executable path"
                    ),
                    result_file=result_file,
                    result_format="nunit-xml",
                )
            )

        return project, profiles

    def _profile(
        self,
        *,
        action: str,
        name: str,
        description: str,
        project_type: str,
        working_directory: str,
        command: Tuple[str, ...],
        display_command: str,
        timeout_seconds: int,
        available: bool,
        unavailable_reason: Optional[str],
        result_file: Optional[str] = None,
        result_format: Optional[str] = None,
    ) -> VerificationProfile:
        identity = f"{project_type}:{action}:{working_directory}"
        suffix = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]

        return VerificationProfile(
            profile_id=f"{project_type}-{action}-{suffix}",
            name=name,
            description=description,
            project_type=project_type,
            working_directory=working_directory,
            command=command,
            display_command=display_command,
            timeout_seconds=timeout_seconds,
            available=available,
            unavailable_reason=unavailable_reason,
            result_file=result_file,
            result_format=result_format,
        )

    @staticmethod
    def _unity_test_framework_declared(directory: Path) -> bool:
        manifest = directory / "Packages" / "manifest.json"
        if not manifest.is_file():
            return False
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return False
        dependencies = payload.get("dependencies")
        return isinstance(dependencies, dict) and isinstance(
            dependencies.get("com.unity.test-framework"), str
        )

    @staticmethod
    def _relative_text(workspace: Path, directory: Path) -> str:
        relative = directory.relative_to(workspace)
        return "." if not relative.parts else relative.as_posix()

    @staticmethod
    def _existing_names(directory: Path, names: Iterable[str]) -> List[str]:
        return [name for name in names if (directory / name).exists()]

    @staticmethod
    def _python_dependency_is_declared(directory: Path, dependency: str) -> bool:
        candidates = [
            directory / "pyproject.toml",
            directory / "requirements.txt",
            directory / "requirements-dev.txt",
        ]
        needle = dependency.lower()

        for candidate in candidates:
            if not candidate.is_file():
                continue
            try:
                if needle in candidate.read_text(encoding="utf-8").lower():
                    return True
            except (OSError, UnicodeDecodeError):
                continue

        return False

    @staticmethod
    def _npm_command_prefix() -> Optional[Tuple[str, ...]]:
        npm_path = shutil.which("npm")
        if not npm_path:
            return None

        if os.name != "nt":
            return (npm_path,)

        node_path = shutil.which("node")
        npm_cli = Path(npm_path).parent / "node_modules" / "npm" / "bin" / "npm-cli.js"
        if node_path and npm_cli.is_file():
            return (node_path, str(npm_cli))

        command_processor = os.environ.get("COMSPEC") or shutil.which("cmd.exe")
        if command_processor:
            return (
                command_processor,
                "/d",
                "/s",
                "/c",
                npm_path,
            )

        return None

    @staticmethod
    def _read_unity_version(project_version: Path) -> Optional[str]:
        try:
            for line in project_version.read_text(encoding="utf-8").splitlines():
                if line.startswith("m_EditorVersion:"):
                    return line.partition(":")[2].strip() or None
        except (OSError, UnicodeDecodeError):
            return None

        return None
