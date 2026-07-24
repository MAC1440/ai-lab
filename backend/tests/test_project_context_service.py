import sqlite3
import tempfile
import unittest
from pathlib import Path

from services.project_context_service import ContextBudget, ProjectContextService
from services.project_detection_service import ProjectDetectionService


class TemporaryWorkspaceService:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def get_workspace(self) -> Path:
        return self.root


class FakeProjectIndexService:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.calls = []

    def query(self, text, *, limit, project_root):
        self.calls.append(
            {
                "text": text,
                "limit": limit,
                "project_root": project_root,
            }
        )
        if self.error:
            raise self.error
        return {
            "results": self.results,
            "tokens": ["inventory"],
            "refresh": {"changed_files": 0},
            "index": {"indexed_at": "2026-07-24T00:00:00+00:00", "file_count": 3},
        }


class ProjectContextServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.workspace_service = TemporaryWorkspaceService(self.root)
        self.detection_service = ProjectDetectionService(self.workspace_service)
        self.service = ProjectContextService(
            self.workspace_service,
            self.detection_service,
            budget=ContextBudget(
                max_total_chars=5000,
                max_file_chars=1200,
                max_files=6,
                max_tree_entries=40,
                max_tree_depth=3,
                max_import_files=2,
            ),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_preloads_prompt_file_manifest_and_direct_import(self):
        frontend = self.root / "frontend"
        component = frontend / "components" / "counter.tsx"
        helper = frontend / "lib" / "math.ts"
        component.parent.mkdir(parents=True)
        helper.parent.mkdir(parents=True)
        (frontend / "package.json").write_text(
            '{"scripts":{"test":"vitest"}}', encoding="utf-8"
        )
        (frontend / "tsconfig.json").write_text(
            '{"compilerOptions":{}}', encoding="utf-8"
        )
        component.write_text(
            'import { add } from "../lib/math";\nexport const total = add(1, 2);',
            encoding="utf-8",
        )
        helper.write_text(
            "export const add = (a: number, b: number) => a + b;",
            encoding="utf-8",
        )

        trace, context = self.service.build(
            prompt=(
                "Fix the error in frontend/components/counter.tsx:2 and "
                "inspect its import."
            ),
            agent_id="web",
        )

        self.assertEqual(trace["selected_project_root"], "frontend")
        self.assertIn("node", trace["project_types"])
        self.assertIn("frontend/components/counter.tsx", trace["files_included"])
        self.assertIn("frontend/package.json", trace["files_included"])
        self.assertIn("frontend/lib/math.ts", trace["files_included"])
        self.assertIn("<workspace_file", context)
        self.assertLessEqual(trace["characters"], 5100)

    def test_converts_absolute_path_inside_workspace(self):
        backend = self.root / "backend"
        target = backend / "tests" / "test_app.py"
        target.parent.mkdir(parents=True)
        (backend / "requirements.txt").write_text("pytest\n", encoding="utf-8")
        target.write_text("def test_ok():\n    assert True\n", encoding="utf-8")

        prompt = (
            f'File "{target}", '
            "line 1"
        )
        trace, _ = self.service.build(prompt=prompt, agent_id="web")

        self.assertIn(
            "backend/tests/test_app.py",
            trace["prompt_paths_found"],
        )

    def test_ignores_paths_outside_workspace(self):
        (self.root / "requirements.txt").write_text("pytest\n", encoding="utf-8")
        trace, context = self.service.build(
            prompt='File "C:\\private\\secrets.py", line 1',
            agent_id="web",
        )

        self.assertEqual(trace["prompt_paths_found"], [])
        self.assertNotIn("secrets.py", context)

    def test_budget_truncates_large_file_and_tree(self):
        (self.root / "requirements.txt").write_text("pytest\n", encoding="utf-8")
        target = self.root / "large.py"
        target.write_text("x = 1\n" * 1000, encoding="utf-8")
        for index in range(60):
            (self.root / f"file_{index}.py").write_text("pass\n", encoding="utf-8")

        trace, context = self.service.build(
            prompt="Inspect large.py",
            agent_id="web",
        )

        self.assertTrue(trace["tree_truncated"])
        self.assertLessEqual(trace["file_count"], 6)
        self.assertLessEqual(len(context), 5100)

    def test_prompt_path_selects_python_root_in_mixed_web_workspace(self):
        backend = self.root / "backend"
        frontend = self.root / "frontend"
        target = backend / "tests" / "test_service.py"
        target.parent.mkdir(parents=True)
        frontend.mkdir()
        (backend / "requirements.txt").write_text("pytest\n", encoding="utf-8")
        (frontend / "package.json").write_text("{}", encoding="utf-8")
        target.write_text("def test_service():\n    assert True\n", encoding="utf-8")

        trace, _ = self.service.build(
            prompt="Repair backend/tests/test_service.py:2",
            agent_id="web",
        )

        self.assertEqual(trace["selected_project_root"], "backend")

    def test_project_index_adds_ranked_current_file_to_planning_context(self):
        frontend = self.root / "frontend"
        component = frontend / "features" / "inventory-panel.tsx"
        component.parent.mkdir(parents=True)
        (frontend / "package.json").write_text("{}", encoding="utf-8")
        component.write_text(
            "export function InventoryPanel() { return null; }\n",
            encoding="utf-8",
        )
        project_index = FakeProjectIndexService(
            results=[
                {
                    "path": "frontend/features/inventory-panel.tsx",
                    "language": "typescript",
                    "score": 60,
                    "reasons": ["symbols: InventoryPanel"],
                    "matching_symbols": ["InventoryPanel"],
                }
            ]
        )
        service = ProjectContextService(
            self.workspace_service,
            self.detection_service,
            project_index_service=project_index,
            budget=self.service.budget,
        )

        trace, context = service.build(
            prompt="Add stock counts to InventoryPanel",
            agent_id="web",
        )

        self.assertIn(
            "frontend/features/inventory-panel.tsx",
            trace["files_included"],
        )
        self.assertIn("InventoryPanel", context)
        self.assertEqual(trace["project_index"]["status"], "ready")
        self.assertEqual(
            project_index.calls[0]["project_root"],
            "frontend",
        )

    def test_project_index_failure_falls_back_to_existing_context(self):
        (self.root / "requirements.txt").write_text(
            "pytest\n",
            encoding="utf-8",
        )
        project_index = FakeProjectIndexService(
            error=sqlite3.OperationalError("index unavailable")
        )
        service = ProjectContextService(
            self.workspace_service,
            self.detection_service,
            project_index_service=project_index,
            budget=self.service.budget,
        )

        trace, context = service.build(
            prompt="Explain this Python project",
            agent_id="web",
        )

        self.assertEqual(trace["project_index"]["status"], "fallback")
        self.assertIn("requirements.txt", context)


if __name__ == "__main__":
    unittest.main()
