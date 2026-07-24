import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.project_index_service import ProjectIndexService


class TemporaryWorkspaceService:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def get_workspace(self) -> Path:
        return self.root


class ProjectIndexServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.workspace = TemporaryWorkspaceService(self.root)
        self.service = ProjectIndexService(
            self.workspace,
            self.root / ".ai-lab-data" / "project-index.sqlite3",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_indexes_symbols_and_ranks_dependency_neighbors(self):
        source = self.root / "src"
        source.mkdir()
        (source / "auth-service.ts").write_text(
            (
                'import { validateSession } from "./session";\n'
                "export class AuthService {}\n"
            ),
            encoding="utf-8",
        )
        (source / "session.ts").write_text(
            "export function validateSession() { return true; }\n",
            encoding="utf-8",
        )
        (source / "unrelated.ts").write_text(
            "export const unrelated = true;\n",
            encoding="utf-8",
        )

        result = self.service.query(
            "Update AuthService authentication session handling",
            limit=5,
        )

        paths = [item["path"] for item in result["results"]]
        self.assertEqual(paths[0], "src/auth-service.ts")
        self.assertIn("src/session.ts", paths)
        session = next(
            item for item in result["results"] if item["path"] == "src/session.ts"
        )
        self.assertTrue(
            any(reason.startswith("dependency of") for reason in session["reasons"])
        )
        self.assertEqual(result["index"]["file_count"], 3)
        self.assertGreaterEqual(result["index"]["symbol_count"], 3)

    def test_incremental_refresh_skips_unchanged_and_removes_deleted_files(self):
        first = self.root / "first.py"
        second = self.root / "second.py"
        first.write_text("class FirstService:\n    pass\n", encoding="utf-8")
        second.write_text("def second_value():\n    return 2\n", encoding="utf-8")

        initial = self.service.refresh()
        repeated = self.service.refresh()
        second.unlink()
        first.write_text(
            "class RenamedService:\n    pass\n",
            encoding="utf-8",
        )
        os.utime(first, None)
        updated = self.service.refresh()
        result = self.service.query(
            "RenamedService",
            refresh=False,
        )

        self.assertEqual(initial["refresh"]["changed_files"], 2)
        self.assertEqual(repeated["refresh"]["changed_files"], 0)
        self.assertEqual(repeated["refresh"]["unchanged_files"], 2)
        self.assertEqual(updated["refresh"]["changed_files"], 1)
        self.assertEqual(updated["refresh"]["removed_files"], 1)
        self.assertEqual(updated["file_count"], 1)
        self.assertEqual(result["results"][0]["path"], "first.py")

    def test_rebuild_reparses_every_indexed_file(self):
        (self.root / "service.py").write_text(
            "class InventoryService:\n    pass\n",
            encoding="utf-8",
        )
        self.service.refresh()

        result = self.service.refresh(rebuild=True)

        self.assertTrue(result["refresh"]["rebuild"])
        self.assertEqual(result["refresh"]["changed_files"], 1)
        self.assertEqual(result["file_count"], 1)

    def test_ignores_generated_directories_and_does_not_store_source(self):
        (self.root / "src").mkdir()
        (self.root / "node_modules").mkdir()
        (self.root / "custom-output").mkdir()
        (self.root / ".gitignore").write_text(
            "custom-output/\n",
            encoding="utf-8",
        )
        secret_marker = "SOURCE_CONTENT_MUST_NOT_BE_PERSISTED"
        (self.root / "src" / "safe.ts").write_text(
            f"export const marker = '{secret_marker}';\n",
            encoding="utf-8",
        )
        (self.root / "node_modules" / "ignored.ts").write_text(
            "export const ignored = true;\n",
            encoding="utf-8",
        )
        (self.root / "custom-output" / "also-ignored.ts").write_text(
            "export const alsoIgnored = true;\n",
            encoding="utf-8",
        )

        result = self.service.refresh()
        database_bytes = self.service.database_path.read_bytes()

        self.assertEqual(result["file_count"], 1)
        self.assertNotIn(secret_marker.encode(), database_bytes)
        self.assertNotIn(b"ignored.ts", database_bytes)
        self.assertNotIn(b"also-ignored.ts", database_bytes)

    def test_project_root_filter_excludes_other_project(self):
        backend = self.root / "backend"
        frontend = self.root / "frontend"
        backend.mkdir()
        frontend.mkdir()
        (backend / "auth.py").write_text(
            "class AuthService:\n    pass\n",
            encoding="utf-8",
        )
        (frontend / "auth.ts").write_text(
            "export class AuthService {}\n",
            encoding="utf-8",
        )

        result = self.service.query(
            "AuthService",
            project_root="backend",
        )

        self.assertEqual(
            [item["path"] for item in result["results"]],
            ["backend/auth.py"],
        )

    def test_resolves_monorepo_absolute_python_and_typescript_aliases(self):
        backend = self.root / "backend" / "services"
        frontend_components = self.root / "frontend" / "components"
        frontend_lib = self.root / "frontend" / "lib"
        backend.mkdir(parents=True)
        frontend_components.mkdir(parents=True)
        frontend_lib.mkdir(parents=True)
        (backend / "auth.py").write_text(
            ("from services.session import Session\nclass AuthService:\n    pass\n"),
            encoding="utf-8",
        )
        (backend / "session.py").write_text(
            "class Session:\n    pass\n",
            encoding="utf-8",
        )
        (frontend_components / "auth-panel.tsx").write_text(
            (
                'import { readSession } from "@/lib/session";\n'
                "export function AuthPanel() { return readSession(); }\n"
            ),
            encoding="utf-8",
        )
        (frontend_lib / "session.ts").write_text(
            "export function readSession() { return null; }\n",
            encoding="utf-8",
        )

        backend_result = self.service.query(
            "Update AuthService",
            project_root="backend",
        )
        frontend_result = self.service.query(
            "Update AuthPanel",
            project_root="frontend",
        )

        self.assertIn(
            "backend/services/session.py",
            [item["path"] for item in backend_result["results"]],
        )
        self.assertIn(
            "frontend/lib/session.ts",
            [item["path"] for item in frontend_result["results"]],
        )

    def test_failed_refresh_is_recorded_without_leaking_source(self):
        (self.root / "service.py").write_text("pass\n", encoding="utf-8")

        with (
            patch.object(
                self.service,
                "_discover",
                side_effect=OSError("simulated scan failure"),
            ),
            self.assertRaisesRegex(OSError, "simulated scan failure"),
        ):
            self.service.refresh()

        status = self.service.status()
        self.assertEqual(status["status"], "attention")
        self.assertIn("simulated scan failure", status["last_error"])


if __name__ == "__main__":
    unittest.main()
