import json
import tempfile
import unittest
from pathlib import Path

from services.project_detection_service import ProjectDetectionService


class TemporaryWorkspaceService:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def get_workspace(self) -> Path:
        return self.root


class ProjectDetectionServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.service = ProjectDetectionService(TemporaryWorkspaceService(self.root))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_detects_python_tests_and_ruff(self):
        backend = self.root / "backend"
        (backend / "tests").mkdir(parents=True)
        (backend / "requirements.txt").write_text(
            "fastapi\n",
            encoding="utf-8",
        )
        (backend / "requirements-dev.txt").write_text(
            "pytest\nruff\n",
            encoding="utf-8",
        )

        result = self.service.inspect_workspace()

        python_project = next(
            project for project in result["projects"] if project["type"] == "python"
        )
        self.assertEqual(python_project["root"], "backend")

        commands = {
            profile["command"]
            for profile in result["profiles"]
            if profile["project_type"] == "python"
        }
        self.assertIn("python -m pytest -q", commands)
        self.assertIn("python -m ruff check .", commands)

    def test_detects_only_declared_node_scripts(self):
        frontend = self.root / "frontend"
        frontend.mkdir()
        (frontend / "package.json").write_text(
            json.dumps(
                {
                    "scripts": {
                        "lint": "eslint",
                        "build": "next build",
                        "dev": "next dev",
                    }
                }
            ),
            encoding="utf-8",
        )

        result = self.service.inspect_workspace()
        node_profiles = [
            profile
            for profile in result["profiles"]
            if profile["project_type"] == "node"
        ]
        commands = {profile["command"] for profile in node_profiles}

        self.assertEqual(
            commands,
            {"npm run lint", "npm run build"},
        )

    def test_unity_profile_explains_missing_editor_configuration(self):
        (self.root / "Assets").mkdir()
        project_settings = self.root / "ProjectSettings"
        project_settings.mkdir()
        (project_settings / "ProjectVersion.txt").write_text(
            "m_EditorVersion: 6000.0.42f1\n",
            encoding="utf-8",
        )

        result = self.service.inspect_workspace()
        unity_project = next(
            project for project in result["projects"] if project["type"] == "unity"
        )
        unity_profile = next(
            profile
            for profile in result["profiles"]
            if profile["project_type"] == "unity"
        )

        self.assertEqual(unity_project["version"], "6000.0.42f1")
        self.assertFalse(unity_profile["available"])
        self.assertIn("UNITY_EDITOR_PATH", unity_profile["unavailable_reason"])

    def test_profile_ids_are_stable(self):
        (self.root / "requirements.txt").write_text(
            "pytest\n",
            encoding="utf-8",
        )
        (self.root / "tests").mkdir()

        first = self.service.inspect_workspace()
        second = self.service.inspect_workspace()

        self.assertEqual(
            [profile["profile_id"] for profile in first["profiles"]],
            [profile["profile_id"] for profile in second["profiles"]],
        )


if __name__ == "__main__":
    unittest.main()
