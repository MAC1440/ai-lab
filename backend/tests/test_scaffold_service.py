import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.change_service import ChangeService
from services.scaffold_service import ScaffoldService


class TemporaryWorkspaceService:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def get_workspace(self):
        return self.root

    def resolve_workspace_path(self, relative_path="."):
        target = (self.root / relative_path).resolve()
        target.relative_to(self.root)
        return target


class ScaffoldServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.workspace = TemporaryWorkspaceService(self.root)
        self.changes = ChangeService(self.workspace)
        self.service = ScaffoldService(self.workspace, self.changes)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_fastapi_scaffold_creates_one_reviewable_change_set(self):
        result = self.service.create_proposals(
            scaffold_id="fastapi",
            target_directory="services/catalog-api",
            project_name="CatalogApi",
        )

        self.assertEqual(result["proposal_count"], 9)
        self.assertTrue(result["requires_approval"])
        self.assertFalse((self.root / "services" / "catalog-api").exists())
        self.assertEqual(
            {proposal["change_set_id"] for proposal in result["proposals"]},
            {result["change_set_id"]},
        )
        self.assertTrue(
            all(proposal["status"] == "pending" for proposal in result["proposals"])
        )

    def test_unity_feature_scaffold_is_namespaced(self):
        result = self.service.create_proposals(
            scaffold_id="unity-feature",
            target_directory="Assets/Features/Inventory",
            project_name="GameInventory",
        )

        paths = {proposal["file_path"].replace("\\", "/") for proposal in result["proposals"]}
        self.assertIn(
            "Assets/Features/Inventory/Runtime/FeatureController.cs",
            paths,
        )
        controller = next(
            proposal for proposal in result["proposals"]
            if proposal["file_path"].endswith("FeatureController.cs")
        )
        self.assertIn("namespace GameInventory", controller["diff"])

    def test_non_empty_target_is_rejected_before_proposals(self):
        target = self.root / "existing"
        target.mkdir()
        (target / "keep.txt").write_text("keep", encoding="utf-8")

        with self.assertRaisesRegex(FileExistsError, "missing or empty"):
            self.service.create_proposals(
                scaffold_id="fastapi",
                target_directory="existing",
                project_name="ExistingApi",
            )
        self.assertEqual(self.changes.list_proposals(), [])

    def test_unsafe_target_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "safe relative"):
            self.service.create_proposals(
                scaffold_id="fastapi",
                target_directory="../outside",
                project_name="UnsafeApi",
            )

    def test_external_generator_output_becomes_proposals(self):
        generated = [
            ("package.json", '{"name":"generated-project"}\n'),
            ("src/main.tsx", "export const app = true;\n"),
        ]
        with patch.object(
            self.service,
            "_run_external_generator",
            return_value=(generated, "generator ok"),
        ):
            result = self.service.create_proposals(
                scaffold_id="vite-react",
                target_directory="apps/dashboard",
                project_name="dashboard",
            )

        self.assertEqual(result["proposal_count"], 2)
        self.assertEqual(result["generator_output"], "generator ok")

    def test_file_limit_rejects_generator_output(self):
        service = ScaffoldService(
            self.workspace,
            self.changes,
            max_files=1,
        )
        with self.assertRaisesRegex(Exception, "limit is 1"):
            service.create_proposals(
                scaffold_id="fastapi",
                target_directory="api",
                project_name="LimitedApi",
            )


if __name__ == "__main__":
    unittest.main()
