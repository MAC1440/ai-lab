import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.conversations import router
from services.agent_service import AgentService
from services.conversation_service import ConversationService
from services.conversation_store import ConversationStore


class Workspace:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def get_workspace(self):
        return self.root


class ConversationRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.service = ConversationService(
            Workspace(root), AgentService(),
            ConversationStore(root / "conversations.sqlite3"),
        )
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self):
        self.temp.cleanup()

    def test_create_list_update_archive_and_delete(self):
        with patch("routes.conversations.conversation_service", self.service):
            created = self.client.post("/conversations", json={"agent_id": "web"})
            self.assertEqual(created.status_code, 200)
            session_id = created.json()["session_id"]
            listed = self.client.get("/conversations")
            self.assertEqual(listed.json()["sessions"][0]["session_id"], session_id)
            renamed = self.client.patch(
                f"/conversations/{session_id}", json={"title": "Renamed"}
            )
            self.assertEqual(renamed.json()["title"], "Renamed")
            archived = self.client.patch(
                f"/conversations/{session_id}", json={"status": "archived"}
            )
            self.assertEqual(archived.json()["status"], "archived")
            self.assertEqual(self.client.delete(f"/conversations/{session_id}").status_code, 204)


if __name__ == "__main__":
    unittest.main()
