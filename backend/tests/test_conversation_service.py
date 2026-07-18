import tempfile
import unittest
from pathlib import Path

from services.agent_service import AgentService
from services.conversation_service import ConversationService, ConversationStateError
from services.conversation_store import ConversationNotFoundError, ConversationStore


class Workspace:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def get_workspace(self):
        return self.root


class ConversationServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = ConversationStore(self.root / "conversations.sqlite3")
        self.service = ConversationService(
            Workspace(self.root), AgentService(), self.store,
            max_model_messages=4, max_model_history_chars=40,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_run_persists_messages_and_automatic_title(self):
        session = self.service.create_session(agent_id="web")
        history = self.service.prepare_run(
            session_id=session["session_id"], agent_id="web",
            prompt="Build a health endpoint", rag_top_k=3,
            rag_distance_threshold=1.0,
        )
        self.assertEqual(history, [])
        self.service.complete_run(
            session_id=session["session_id"],
            result={"answer": "Proposal ready", "agent_id": "web"},
        )
        saved = self.service.get_session(session["session_id"])
        self.assertEqual(saved["title"], "Build a health endpoint")
        self.assertEqual([item["role"] for item in saved["messages"]], ["user", "assistant"])
        self.assertEqual(saved["messages"][1]["agent_result"]["agent_id"], "web")

    def test_model_history_is_bounded_but_full_transcript_remains(self):
        session = self.service.create_session(agent_id="coding")
        for index in range(4):
            self.store.add_message({
                "message_id": f"m-{index}", "session_id": session["session_id"],
                "role": "user" if index % 2 == 0 else "assistant",
                "content": f"message-{index}-" + ("x" * 20),
                "created_at": f"2026-01-01T00:00:0{index}+00:00",
            })
        history = self.service.model_history(session["session_id"])
        self.assertLessEqual(sum(len(item["content"]) for item in history), 40)
        self.assertEqual(len(self.service.get_session(session["session_id"])["messages"]), 4)

    def test_agent_mismatch_and_archived_session_are_rejected(self):
        session = self.service.create_session(agent_id="web")
        with self.assertRaisesRegex(ConversationStateError, "does not match"):
            self.service.prepare_run(
                session_id=session["session_id"], agent_id="unity",
                prompt="hello", rag_top_k=3, rag_distance_threshold=1.0,
            )
        self.service.update_session(session["session_id"], status="archived")
        with self.assertRaisesRegex(ConversationStateError, "read-only"):
            self.service.prepare_run(
                session_id=session["session_id"], agent_id="web",
                prompt="hello", rag_top_k=3, rag_distance_threshold=1.0,
            )

    def test_delete_cascades_messages(self):
        session = self.service.create_session(agent_id="general")
        self.store.add_message({
            "message_id": "message", "session_id": session["session_id"],
            "role": "user", "content": "hello", "created_at": "now",
        })
        self.service.delete_session(session["session_id"])
        with self.assertRaises(ConversationNotFoundError):
            self.service.get_session(session["session_id"])
        self.assertEqual(self.store.list_messages(session["session_id"]), [])


if __name__ == "__main__":
    unittest.main()
