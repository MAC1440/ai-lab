import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.change_service import ChangeService
from tools import file_tools


class TemporaryWorkspaceService:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def get_workspace(self) -> Path:
        return self.root

    def resolve_workspace_path(self, relative_path: str = ".") -> Path:
        target = (self.root / relative_path).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as error:
            raise PermissionError(
                "Access outside the active workspace is not allowed"
            ) from error
        return target


class FileProposalToolTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.workspace = TemporaryWorkspaceService(self.root)
        self.change_service = ChangeService(self.workspace)
        self.patches = [
            patch.object(file_tools, "workspace_service", self.workspace),
            patch.object(file_tools, "change_service", self.change_service),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.temp_dir.cleanup()

    def test_exact_replacement_creates_diff_without_writing(self):
        target = self.root / "app.py"
        target.write_text(
            "def answer():\n    return 41\n",
            encoding="utf-8",
        )

        result = file_tools.propose_file_change(
            file_path="app.py",
            old_text="    return 41\n",
            new_text="    return 42\n",
            summary="Correct the answer",
        )

        proposal = result["proposal"]
        self.assertEqual(proposal["status"], "pending")
        self.assertIn("-    return 41", proposal["diff"])
        self.assertIn("+    return 42", proposal["diff"])
        self.assertEqual(
            target.read_text(encoding="utf-8"),
            "def answer():\n    return 41\n",
        )

    def test_ambiguous_old_text_is_rejected(self):
        (self.root / "app.txt").write_text(
            "same\nsame\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "exactly once"):
            file_tools.propose_file_change(
                file_path="app.txt",
                old_text="same",
                new_text="changed",
            )

    def test_lf_tool_text_matches_crlf_file_without_mixing_newlines(self):
        target = self.root / "windows.py"
        target.write_bytes(b"def answer():\r\n    return 41\r\n")

        result = file_tools.propose_file_change(
            file_path="windows.py",
            old_text="    return 41\n",
            new_text="    return 42\n",
            summary="Correct the answer",
        )

        proposal = result["proposal"]
        self.assertIn("-    return 41", proposal["diff"])
        self.assertIn("+    return 42", proposal["diff"])
        self.assertEqual(
            target.read_bytes(),
            b"def answer():\r\n    return 41\r\n",
        )

        self.change_service.approve(proposal["proposal_id"])
        self.assertEqual(
            target.read_bytes(),
            b"def answer():\r\n    return 42\r\n",
        )

    def test_empty_old_text_creates_new_file_proposal(self):
        result = file_tools.propose_file_change(
            file_path="new.txt",
            old_text="",
            new_text="hello\n",
        )

        proposal = result["proposal"]
        self.assertEqual(proposal["operation"], "create")
        self.assertFalse((self.root / "new.txt").exists())


if __name__ == "__main__":
    unittest.main()
