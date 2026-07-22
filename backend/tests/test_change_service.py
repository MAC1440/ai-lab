import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_generated_change_set_proposals_are_all_or_nothing(self):
        existing = self.root / "existing.py"
        existing.write_text("unchanged = True\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "identical"):
            self.service.propose_change_set(
                change_set_id="generated-set",
                operations=[
                    {
                        "path": "new.py",
                        "operation": "create",
                        "summary": "Create the first file.",
                        "content": "created = True\n",
                    },
                    {
                        "path": "existing.py",
                        "operation": "update",
                        "summary": "Invalid no-op update.",
                        "content": "unchanged = True\n",
                    },
                ],
            )

        self.assertEqual(
            self.service.list_proposals(change_set_id="generated-set"),
            [],
        )
        self.assertFalse((self.root / "new.py").exists())

    def test_change_set_rejects_identical_update_during_preflight(self):
        existing = self.root / "existing.py"
        existing.write_text("unchanged = True\n", encoding="utf-8")

        with patch.object(
            self.service,
            "propose",
            wraps=self.service.propose,
        ) as propose:
            with self.assertRaisesRegex(ValueError, "identical"):
                self.service.propose_change_set(
                    change_set_id="preflight-set",
                    operations=[
                        {
                            "path": "existing.py",
                            "operation": "update",
                            "summary": "Invalid no-op update.",
                            "content": "unchanged = True\n",
                        }
                    ],
                )

        propose.assert_not_called()
        self.assertEqual(
            self.service.list_proposals(change_set_id="preflight-set"),
            [],
        )

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

    def test_proposals_survive_service_restart_with_sqlite(self):
        database_path = self.root / "changes.sqlite3"
        first = ChangeService(self.workspace, database_path=database_path)
        proposal = first.propose(
            file_path="persistent.txt",
            content="hello\n",
            change_set_id="set-1",
            repair_task_id="repair-1",
        )

        second = ChangeService(self.workspace, database_path=database_path)
        restored = second.get(proposal["proposal_id"])

        self.assertEqual(restored["file_path"], "persistent.txt")
        self.assertEqual(restored["change_set_id"], "set-1")
        self.assertEqual(restored["repair_task_id"], "repair-1")

    def test_list_can_filter_change_set_and_repair_task(self):
        self.service.propose(
            file_path="one.txt",
            content="one\n",
            change_set_id="set-a",
            repair_task_id="repair-a",
        )
        self.service.propose(
            file_path="two.txt",
            content="two\n",
            change_set_id="set-b",
            repair_task_id="repair-b",
        )

        self.assertEqual(
            len(self.service.list_proposals(change_set_id="set-a")),
            1,
        )
        self.assertEqual(
            len(self.service.list_proposals(repair_task_id="repair-b")),
            1,
        )

    def test_approve_change_set_writes_every_file(self):
        for name in ("one.txt", "two.txt"):
            self.service.propose(
                file_path=name,
                content=f"{name}\n",
                change_set_id="set-a",
            )

        resolved = self.service.approve_change_set("set-a")

        self.assertEqual({item["status"] for item in resolved}, {"approved"})
        self.assertEqual((self.root / "one.txt").read_text(), "one.txt\n")
        self.assertEqual((self.root / "two.txt").read_text(), "two.txt\n")

    def test_change_set_preflights_all_files_before_first_write(self):
        first = self.root / "one.txt"
        second = self.root / "two.txt"
        first.write_text("old one\n", encoding="utf-8")
        second.write_text("old two\n", encoding="utf-8")
        self.service.propose(
            file_path="one.txt", content="new one\n", change_set_id="set-a"
        )
        self.service.propose(
            file_path="two.txt", content="new two\n", change_set_id="set-a"
        )
        second.write_text("changed elsewhere\n", encoding="utf-8")

        with self.assertRaises(ChangeProposalConflictError):
            self.service.approve_change_set("set-a")

        self.assertEqual(first.read_text(encoding="utf-8"), "old one\n")
        self.assertEqual(
            {item["status"] for item in self.service.list_proposals(
                change_set_id="set-a"
            )},
            {"pending"},
        )

    def test_change_set_rejects_duplicate_targets(self):
        (self.root / "one.txt").write_text("old\n", encoding="utf-8")
        self.service.propose(
            file_path="one.txt", content="first\n", change_set_id="set-a"
        )
        self.service.propose(
            file_path="one.txt", content="second\n", change_set_id="set-a"
        )
        with self.assertRaisesRegex(
            ChangeProposalConflictError, "same path more than once"
        ):
            self.service.approve_change_set("set-a")
        self.assertEqual(
            (self.root / "one.txt").read_text(encoding="utf-8"), "old\n"
        )

    def test_change_set_rolls_back_when_second_write_fails(self):
        first = self.root / "one.txt"
        second = self.root / "two.txt"
        first.write_text("old one\n", encoding="utf-8")
        second.write_text("old two\n", encoding="utf-8")
        self.service.propose(
            file_path="one.txt", content="new one\n", change_set_id="set-a"
        )
        self.service.propose(
            file_path="two.txt", content="new two\n", change_set_id="set-a"
        )
        original_apply = self.service._apply_proposal
        call_count = 0

        def fail_second(proposal, target):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise OSError("simulated disk failure")
            original_apply(proposal, target)

        with patch.object(
            self.service, "_apply_proposal", side_effect=fail_second
        ):
            with self.assertRaisesRegex(OSError, "simulated disk failure"):
                self.service.approve_change_set("set-a")

        self.assertEqual(first.read_text(encoding="utf-8"), "old one\n")
        self.assertEqual(second.read_text(encoding="utf-8"), "old two\n")
        self.assertEqual(
            {item["status"] for item in self.service.list_proposals(
                change_set_id="set-a"
            )},
            {"pending"},
        )

    def test_reject_change_set_keeps_files_unchanged(self):
        self.service.propose(
            file_path="one.txt",
            content="one\n",
            change_set_id="set-a",
        )
        resolved = self.service.reject_change_set("set-a")

        self.assertEqual(resolved[0]["status"], "rejected")
        self.assertFalse((self.root / "one.txt").exists())

    def test_approved_delete_removes_file(self):
        target = self.root / "obsolete.txt"
        target.write_text("old\n", encoding="utf-8")
        proposal = self.service.propose_delete(file_path="obsolete.txt")
        self.service.approve(proposal["proposal_id"])
        self.assertFalse(target.exists())

    def test_stale_delete_is_blocked(self):
        target = self.root / "obsolete.txt"
        target.write_text("old\n", encoding="utf-8")
        proposal = self.service.propose_delete(file_path="obsolete.txt")
        target.write_text("changed\n", encoding="utf-8")
        with self.assertRaises(ChangeProposalConflictError):
            self.service.approve(proposal["proposal_id"])

    def test_approved_move_renames_file(self):
        source = self.root / "old.txt"
        source.write_text("content\n", encoding="utf-8")
        proposal = self.service.propose_move(
            file_path="old.txt",
            destination_path="nested/new.txt",
        )
        self.service.approve(proposal["proposal_id"])
        self.assertFalse(source.exists())
        self.assertEqual(
            (self.root / "nested/new.txt").read_text(encoding="utf-8"),
            "content\n",
        )

    def test_move_rejects_existing_destination(self):
        (self.root / "old.txt").write_text("old\n", encoding="utf-8")
        (self.root / "new.txt").write_text("new\n", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.service.propose_move(
                file_path="old.txt",
                destination_path="new.txt",
            )

    def test_approved_mkdir_creates_directory(self):
        proposal = self.service.propose_directory(
            directory_path="src/generated"
        )
        self.service.approve(proposal["proposal_id"])
        self.assertTrue((self.root / "src/generated").is_dir())

    def test_directory_delete_is_not_supported(self):
        (self.root / "folder").mkdir()
        with self.assertRaises(IsADirectoryError):
            self.service.propose_delete(file_path="folder")


if __name__ == "__main__":
    unittest.main()
