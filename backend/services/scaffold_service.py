from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import uuid4

from services.change_service import ChangeService
from services.workspace_service import WorkspaceService


IGNORED_GENERATED_DIRECTORIES = {
    ".git",
    ".next",
    "dist",
    "Library",
    "node_modules",
    "obj",
    "Temp",
}


class ScaffoldUnavailableError(RuntimeError):
    """Raised when a required established generator is unavailable."""


class ScaffoldGenerationError(RuntimeError):
    """Raised when a generator fails or produces unsafe output."""


@dataclass(frozen=True)
class ScaffoldDefinition:
    scaffold_id: str
    name: str
    description: str
    project_type: str
    source: str
    requires_network: bool
    default_directory: str

    def public(self, *, available: bool, unavailable_reason: Optional[str]) -> Dict[str, Any]:
        return {
            "scaffold_id": self.scaffold_id,
            "name": self.name,
            "description": self.description,
            "project_type": self.project_type,
            "source": self.source,
            "requires_network": self.requires_network,
            "default_directory": self.default_directory,
            "available": available,
            "unavailable_reason": unavailable_reason,
        }


SCAFFOLDS = {
    "nextjs": ScaffoldDefinition(
        scaffold_id="nextjs",
        name="Next.js TypeScript App",
        description="Official create-next-app output with App Router, Tailwind and ESLint.",
        project_type="node",
        source="create-next-app@latest",
        requires_network=True,
        default_directory="web-app",
    ),
    "vite-react": ScaffoldDefinition(
        scaffold_id="vite-react",
        name="Vite React TypeScript App",
        description="Official create-vite React TypeScript starter.",
        project_type="node",
        source="create-vite@latest",
        requires_network=True,
        default_directory="react-app",
    ),
    "fastapi": ScaffoldDefinition(
        scaffold_id="fastapi",
        name="FastAPI Service",
        description="Small AI Lab FastAPI starter with settings, health route and tests.",
        project_type="python",
        source="AI Lab curated template",
        requires_network=False,
        default_directory="api",
    ),
    "unity-feature": ScaffoldDefinition(
        scaffold_id="unity-feature",
        name="Unity Gameplay Feature",
        description="A namespaced Unity C# feature folder with assembly definition and tests.",
        project_type="unity",
        source="AI Lab curated template",
        requires_network=False,
        default_directory="Assets/Features/NewFeature",
    ),
}


class ScaffoldService:
    """Stage trusted scaffolds and convert every generated file to proposals."""

    def __init__(
        self,
        workspace_service: WorkspaceService,
        change_service: ChangeService,
        *,
        max_files: int = 100,
        max_total_bytes: int = 2_000_000,
        generator_timeout_seconds: int = 300,
    ) -> None:
        if max_files < 1 or max_total_bytes < 1:
            raise ValueError("Scaffold limits must be positive")
        self.workspace_service = workspace_service
        self.change_service = change_service
        self.max_files = max_files
        self.max_total_bytes = max_total_bytes
        self.generator_timeout_seconds = generator_timeout_seconds

    def list_scaffolds(self) -> List[Dict[str, Any]]:
        npx = shutil.which("npx") or shutil.which("npx.cmd")
        results = []
        for definition in SCAFFOLDS.values():
            external = definition.scaffold_id in {"nextjs", "vite-react"}
            available = not external or npx is not None
            results.append(
                definition.public(
                    available=available,
                    unavailable_reason=(
                        None if available else "Install Node.js/npm so npx is available"
                    ),
                )
            )
        return results

    def create_proposals(
        self,
        *,
        scaffold_id: str,
        target_directory: str,
        project_name: str,
    ) -> Dict[str, Any]:
        definition = SCAFFOLDS.get(scaffold_id.strip())
        if definition is None:
            raise ValueError(f"Unknown scaffold: {scaffold_id}")
        clean_target = self._validate_target(target_directory)
        clean_name = self._validate_project_name(project_name)
        target = self.workspace_service.resolve_workspace_path(clean_target)
        if target.exists():
            if not target.is_dir() or any(target.iterdir()):
                raise FileExistsError(
                    f"Scaffold target must be missing or empty: {clean_target}"
                )

        if definition.scaffold_id in {"nextjs", "vite-react"}:
            files, generator_output = self._run_external_generator(
                definition.scaffold_id,
                clean_name,
            )
        else:
            files = self._built_in_files(definition.scaffold_id, clean_name)
            generator_output = "Built from the bundled reviewed template."

        self._validate_generated_files(files)
        for relative_path, _ in files:
            destination = self.workspace_service.resolve_workspace_path(
                str(Path(clean_target) / relative_path)
            )
            if destination.exists():
                raise FileExistsError(
                    "Generated file would overwrite an existing path: "
                    f"{destination.relative_to(self.workspace_service.get_workspace())}"
                )

        change_set_id = uuid4().hex
        proposals = [
            self.change_service.propose(
                file_path=str(Path(clean_target) / relative_path),
                content=content,
                summary=f"Scaffold {definition.name}: {relative_path}",
                change_set_id=change_set_id,
            )
            for relative_path, content in files
        ]
        return {
            "scaffold_id": definition.scaffold_id,
            "name": definition.name,
            "target_directory": clean_target,
            "change_set_id": change_set_id,
            "proposal_count": len(proposals),
            "proposals": proposals,
            "generator_output": generator_output[-4000:],
            "requires_approval": True,
        }

    def _run_external_generator(
        self,
        scaffold_id: str,
        project_name: str,
    ) -> Tuple[List[Tuple[str, str]], str]:
        npx = shutil.which("npx") or shutil.which("npx.cmd")
        if not npx:
            raise ScaffoldUnavailableError(
                "npx was not found. Install Node.js/npm or use an offline scaffold."
            )
        safe_folder = "generated-project"
        if scaffold_id == "nextjs":
            command = (
                npx,
                "--yes",
                "create-next-app@latest",
                safe_folder,
                "--ts",
                "--eslint",
                "--tailwind",
                "--app",
                "--src-dir",
                "--use-npm",
                "--skip-install",
                "--yes",
            )
        else:
            command = (
                npx,
                "--yes",
                "create-vite@latest",
                safe_folder,
                "--template",
                "react-ts",
            )
        with tempfile.TemporaryDirectory(prefix="ai-lab-scaffold-") as temp:
            try:
                result = subprocess.run(
                    command,
                    cwd=temp,
                    capture_output=True,
                    text=True,
                    timeout=self.generator_timeout_seconds,
                    check=False,
                    shell=False,
                    env={**os.environ, "CI": "1", "NO_COLOR": "1"},
                )
            except subprocess.TimeoutExpired as error:
                raise ScaffoldGenerationError(
                    "The scaffold generator timed out"
                ) from error
            except OSError as error:
                raise ScaffoldUnavailableError(str(error)) from error
            output = "\n".join(part for part in (result.stdout, result.stderr) if part)
            if result.returncode != 0:
                raise ScaffoldGenerationError(
                    f"Generator exited with code {result.returncode}:\n{output[-4000:]}"
                )
            root = Path(temp) / safe_folder
            if not root.is_dir():
                raise ScaffoldGenerationError(
                    "Generator completed without creating the expected project"
                )
            files = self._collect_text_files(root)
            return self._replace_project_name(files, safe_folder, project_name), output

    def _collect_text_files(self, root: Path) -> List[Tuple[str, str]]:
        files: List[Tuple[str, str]] = []
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if any(part in IGNORED_GENERATED_DIRECTORIES for part in relative.parts):
                continue
            if not path.is_file() or path.is_symlink():
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            files.append((relative.as_posix(), content))
        return files

    @staticmethod
    def _replace_project_name(
        files: Sequence[Tuple[str, str]],
        generated_name: str,
        project_name: str,
    ) -> List[Tuple[str, str]]:
        return [
            (path, content.replace(generated_name, project_name))
            for path, content in files
        ]

    def _validate_generated_files(self, files: Sequence[Tuple[str, str]]) -> None:
        if not files:
            raise ScaffoldGenerationError("The scaffold produced no text files")
        if len(files) > self.max_files:
            raise ScaffoldGenerationError(
                f"Scaffold produced {len(files)} files; limit is {self.max_files}"
            )
        total_bytes = sum(len(content.encode("utf-8")) for _, content in files)
        if total_bytes > self.max_total_bytes:
            raise ScaffoldGenerationError(
                f"Scaffold produced {total_bytes} bytes; limit is {self.max_total_bytes}"
            )
        for path, _ in files:
            candidate = Path(path)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise ScaffoldGenerationError(
                    f"Generator produced an unsafe path: {path}"
                )

    @staticmethod
    def _validate_target(target: str) -> str:
        if not isinstance(target, str) or not target.strip():
            raise ValueError("target_directory must be a non-empty relative path")
        clean = target.strip().replace("\\", "/").strip("/")
        path = Path(clean)
        if path.is_absolute() or ".." in path.parts or clean in {"", "."}:
            raise ValueError("target_directory must be a safe relative subdirectory")
        return path.as_posix()

    @staticmethod
    def _validate_project_name(name: str) -> str:
        clean = name.strip() if isinstance(name, str) else ""
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{1,49}", clean):
            raise ValueError(
                "project_name must start with a letter and contain 2-50 letters, numbers, dashes or underscores"
            )
        return clean

    @staticmethod
    def _built_in_files(scaffold_id: str, project_name: str) -> List[Tuple[str, str]]:
        if scaffold_id == "fastapi":
            return _fastapi_files(project_name)
        if scaffold_id == "unity-feature":
            return _unity_feature_files(project_name)
        raise ValueError(f"No built-in template for {scaffold_id}")


def _fastapi_files(project_name: str) -> List[Tuple[str, str]]:
    package = re.sub(r"[^a-z0-9_]", "_", project_name.lower().replace("-", "_"))
    return [
        ("requirements.txt", "fastapi>=0.115,<1.0\nuvicorn[standard]>=0.30,<1.0\npydantic-settings>=2.7,<3.0\n"),
        ("requirements-dev.txt", "-r requirements.txt\npytest>=8.0,<9.0\nhttpx>=0.28,<1.0\nruff>=0.9,<1.0\n"),
        (".env.example", f"APP_NAME={project_name}\nAPP_ENV=development\n"),
        ("app/__init__.py", ""),
        ("app/config.py", "from pydantic_settings import BaseSettings, SettingsConfigDict\n\n\nclass Settings(BaseSettings):\n    app_name: str = \"FastAPI Service\"\n    app_env: str = \"development\"\n    model_config = SettingsConfigDict(env_file=\".env\", extra=\"ignore\")\n\n\nsettings = Settings()\n"),
        ("app/main.py", "from fastapi import FastAPI\n\nfrom app.config import settings\n\n\ndef create_app() -> FastAPI:\n    app = FastAPI(title=settings.app_name)\n\n    @app.get(\"/health\")\n    def health() -> dict[str, str]:\n        return {\"status\": \"ok\", \"environment\": settings.app_env}\n\n    return app\n\n\napp = create_app()\n"),
        ("tests/test_health.py", "from fastapi.testclient import TestClient\n\nfrom app.main import app\n\n\ndef test_health() -> None:\n    response = TestClient(app).get(\"/health\")\n    assert response.status_code == 200\n    assert response.json()[\"status\"] == \"ok\"\n"),
        ("README.md", f"# {project_name}\n\n```powershell\npython -m venv .venv\n.venv\\Scripts\\activate\npip install -r requirements-dev.txt\nuvicorn app.main:app --reload\n```\n\nRun tests with `python -m pytest -q`.\n"),
        ("pyproject.toml", f"[project]\nname = \"{package}\"\nversion = \"0.1.0\"\nrequires-python = \">=3.11\"\n\n[tool.pytest.ini_options]\ntestpaths = [\"tests\"]\n\n[tool.ruff]\nline-length = 88\ntarget-version = \"py311\"\n"),
    ]


def _unity_feature_files(project_name: str) -> List[Tuple[str, str]]:
    namespace = re.sub(r"[^A-Za-z0-9]", "", project_name)
    return [
        (f"{namespace}.asmdef", f'{{\n  "name": "{namespace}",\n  "rootNamespace": "{namespace}",\n  "references": [],\n  "autoReferenced": true\n}}\n'),
        ("Runtime/FeatureController.cs", f"using UnityEngine;\n\nnamespace {namespace}\n{{\n    public sealed class FeatureController : MonoBehaviour\n    {{\n        [SerializeField] private bool isEnabled = true;\n\n        public bool IsEnabled => isEnabled;\n\n        public void SetEnabled(bool value)\n        {{\n            isEnabled = value;\n        }}\n    }}\n}}\n"),
        ("Runtime/FeatureSettings.cs", f"using UnityEngine;\n\nnamespace {namespace}\n{{\n    [CreateAssetMenu(menuName = \"{namespace}/Settings\", fileName = \"{namespace}Settings\")]\n    public sealed class FeatureSettings : ScriptableObject\n    {{\n        [Min(0f)] public float updateInterval = 0.25f;\n    }}\n}}\n"),
        ("Tests/EditMode/FeatureControllerTests.cs", f"using NUnit.Framework;\nusing UnityEngine;\n\nnamespace {namespace}.Tests\n{{\n    public sealed class FeatureControllerTests\n    {{\n        [Test]\n        public void SetEnabled_UpdatesState()\n        {{\n            var gameObject = new GameObject(\"FeatureControllerTest\");\n            try\n            {{\n                var controller = gameObject.AddComponent<FeatureController>();\n                controller.SetEnabled(false);\n                Assert.That(controller.IsEnabled, Is.False);\n            }}\n            finally\n            {{\n                Object.DestroyImmediate(gameObject);\n            }}\n        }}\n    }}\n}}\n"),
        ("README.md", f"# {project_name}\n\nA reviewable Unity feature scaffold. Create a `{namespace}Settings` asset from the Create Asset menu and attach `FeatureController` where needed.\n"),
    ]
