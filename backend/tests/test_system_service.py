import sqlite3
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

from services.system_service import SystemService


class SystemServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()

        workspace_service = Mock()
        workspace_service.get_workspace_info.return_value = {
            "workspace": str(self.workspace)
        }
        provider_service = Mock()
        provider_service.get_provider.return_value = {
            "base_url": "http://localhost:11434"
        }
        provider_service.resolve_agent.return_value = {
            "provider_id": "ollama",
            "model": "granite4.1:3b",
        }
        mcp_service = Mock()
        mcp_service.snapshot.return_value = {"servers": []}

        self.database = self.root / "changes.sqlite3"
        connection = sqlite3.connect(self.database)
        connection.execute("CREATE TABLE proposals (id TEXT PRIMARY KEY)")
        connection.commit()
        connection.close()

        self.config = self.root / "provider-settings.json"
        self.config.write_text('{"version": 1}\n', encoding="utf-8")
        self.service = SystemService(
            workspace_service=workspace_service,
            provider_settings_service=provider_service,
            mcp_service=mcp_service,
            agent_ids=["coding"],
            database_paths={"changes": self.database},
            config_paths={"provider-settings": self.config},
            data_directory=self.root / "data",
        )

    def tearDown(self):
        self.temporary.cleanup()

    @patch("services.system_service.httpx.get")
    def test_diagnostics_reports_healthy_local_services(self, get):
        get.return_value.raise_for_status.return_value = None
        get.return_value.json.return_value = {
            "models": [{"name": "granite4.1:3b"}]
        }

        result = self.service.diagnostics()

        self.assertEqual(result["summary"]["failed"], 0)
        checks = {item["id"]: item for item in result["checks"]}
        self.assertEqual(checks["ollama"]["status"], "pass")
        self.assertEqual(checks["db-changes"]["status"], "pass")

    def test_backup_contains_consistent_database_and_no_secrets(self):
        _, content = self.service.create_backup()

        with zipfile.ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())
            self.assertIn("manifest.json", names)
            self.assertIn("databases/changes.sqlite3", names)
            self.assertIn("config/provider-settings.json", names)
            manifest = archive.read("manifest.json").decode("utf-8")
            self.assertIn('"contains_api_keys": false', manifest)


if __name__ == "__main__":
    unittest.main()
