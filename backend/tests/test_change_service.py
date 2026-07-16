import tempfile
import unittest
from pathlib import Path

from services.change_service import (
    ChangeProposalConflictError,
    ChangeProposalStateError,
    ChangeService,
)


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


class ChangeServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.workspace = TemporaryWorkspaceService(self.root)
        self.service = ChangeService(self.workspace)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_proposal_does_not_write_until_approved(self):
        target = self.root / "example.py"
        target.write_text("old = True\n", encoding="utf-8")

        proposal = self.service.propose(
            file_path="example.py",
            content="old = False\n",
            summary="Update the flag",
        )

        self.assertEqual(target.read_text(encoding="utf-8"), "old = True\n")
        self.assertEqual(proposal["status"], "pending")
        self.assertIn("-old = True", proposal["diff"])
        self.assertIn("+old = False", proposal["diff"])

        approved = self.service.approve(proposal["proposal_id"])
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(target.read_text(encoding="utf-8"), "old = False\n")

    def test_reject_never_writes(self):
        target = self.root / "example.txt"
        target.write_text("before\n", encoding="utf-8")
        proposal = self.service.propose(
            file_path="example.txt",
            content="after\n",
        )

        rejected = self.service.reject(proposal["proposal_id"])
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(target.read_text(encoding="utf-8"), "before\n")

        with self.assertRaises(ChangeProposalStateError):
            self.service.approve(proposal["proposal_id"])

    def test_stale_file_blocks_approval(self):
        target = self.root / "example.txt"
        target.write_text("one\n", encoding="utf-8")
        proposal = self.service.propose(
            file_path="example.txt",
            content="two\n",
        )
        target.write_text("changed elsewhere\n", encoding="utf-8")

        with self.assertRaises(ChangeProposalConflictError):
            self.service.approve(proposal["proposal_id"])

        self.assertEqual(
            target.read_text(encoding="utf-8"),
            "changed elsewhere\n",
        )

    def test_can_propose_and_approve_new_file(self):
        proposal = self.service.propose(
            file_path="nested/new.txt",
            content="created\n",
        )
        self.assertEqual(proposal["operation"], "create")
        self.assertFalse((self.root / "nested/new.txt").exists())

        self.service.approve(proposal["proposal_id"])
        self.assertEqual(
            (self.root / "nested/new.txt").read_text(encoding="utf-8"),
            "created\n",
        )

    def test_path_traversal_is_rejected(self):
        with self.assertRaises(PermissionError):
            self.service.propose(
                file_path="../outside.txt",
                content="nope",
            )


if __name__ == "__main__":
    unittest.main()
