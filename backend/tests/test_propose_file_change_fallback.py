from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from services.change_service import ChangeService
from services.workspace_service import WorkspaceService
from tools import file_tools


class ProposeFileChangeFallbackTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        self.workspace_service = WorkspaceService()
        self.workspace_service.set_workspace(str(self.workspace))
        self.change_service = ChangeService(self.workspace_service)

        self.workspace_patch = patch.object(
            file_tools,
            "workspace_service",
            self.workspace_service,
        )
        self.change_patch = patch.object(
            file_tools,
            "change_service",
            self.change_service,
        )
        self.workspace_patch.start()
        self.change_patch.start()

    def tearDown(self) -> None:
        self.change_patch.stop()
        self.workspace_patch.stop()
        self.temp_dir.cleanup()

    def test_missing_old_text_uses_full_file_mode(self) -> None:
        target = self.workspace / "Collision.cs"
        target.write_text("buggy code\n", encoding="utf-8")

        result = file_tools.propose_file_change(
            file_path="Collision.cs",
            new_text="fixed code\n",
            summary="Fix collision handling",
        )

        proposal = result["proposal"]
        self.assertEqual(proposal["status"], "pending")
        self.assertIn("-buggy code", proposal["diff"])
        self.assertIn("+fixed code", proposal["diff"])
        self.assertEqual(target.read_text(encoding="utf-8"), "buggy code\n")

    def test_exact_replacement_mode_still_works(self) -> None:
        target = self.workspace / "Collision.cs"
        target.write_text("before\nbug\nafter\n", encoding="utf-8")

        result = file_tools.propose_file_change(
            file_path="Collision.cs",
            old_text="bug\n",
            new_text="fixed\n",
        )

        proposal = result["proposal"]
        self.assertIn("-bug", proposal["diff"])
        self.assertIn("+fixed", proposal["diff"])
