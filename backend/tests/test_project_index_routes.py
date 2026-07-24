import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.project_index import router
from services.project_index_service import ProjectIndexService


class TemporaryWorkspaceService:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def get_workspace(self) -> Path:
        return self.root


class ProjectIndexRoutesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        workspace = TemporaryWorkspaceService(self.root)
        self.service = ProjectIndexService(
            workspace,
            self.root / "index.sqlite3",
        )
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.service_patch = patch(
            "routes.project_index.project_index_service",
            self.service,
        )
        self.service_patch.start()

    def tearDown(self):
        self.service_patch.stop()
        self.client.close()
        self.temp_dir.cleanup()

    def test_status_refresh_and_query_routes(self):
        (self.root / "inventory.py").write_text(
            "class InventoryService:\n    pass\n",
            encoding="utf-8",
        )

        initial = self.client.get("/project-index/status")
        refreshed = self.client.post(
            "/project-index/refresh",
            json={"rebuild": False},
        )
        queried = self.client.post(
            "/project-index/query",
            json={
                "query": "InventoryService",
                "limit": 5,
                "refresh": False,
            },
        )

        self.assertEqual(initial.status_code, 200)
        self.assertEqual(initial.json()["status"], "not_indexed")
        self.assertEqual(refreshed.status_code, 200)
        self.assertEqual(refreshed.json()["file_count"], 1)
        self.assertEqual(queried.status_code, 200)
        self.assertEqual(
            queried.json()["results"][0]["path"],
            "inventory.py",
        )

    def test_query_rejects_invalid_limit(self):
        response = self.client.post(
            "/project-index/query",
            json={"query": "inventory", "limit": 0},
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
