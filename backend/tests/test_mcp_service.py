import tempfile
import unittest
from pathlib import Path

from services.mcp_service import MCPServerInput, MCPService


class MCPServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.service = MCPService(
            Path(self.temp_dir.name) / "mcp-settings.json"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def save_server(self, **overrides):
        values = {
            "name": "Documentation",
            "url": "http://127.0.0.1:8001/mcp",
            "enabled": True,
            "tool_prefix": "docs",
            "allowed_tools": ["search", "read"],
            "agent_ids": ["coding"],
            **overrides,
        }
        return self.service.save_server(
            "docs",
            MCPServerInput(**values),
            valid_agent_ids={"general", "coding", "web", "unity"},
        )

    def test_new_service_has_no_servers(self):
        self.assertEqual(self.service.snapshot(), {"servers": []})

    def test_saves_explicit_agent_and_tool_allowlists(self):
        server = self.save_server()
        self.assertEqual(server["allowed_tools"], ["read", "search"])
        self.assertEqual(server["agent_ids"], ["coding"])
        restored = self.service.snapshot()["servers"][0]
        self.assertEqual(restored, server)

    def test_server_without_allowed_tools_builds_no_toolset(self):
        self.save_server(allowed_tools=[])
        self.assertEqual(self.service.build_toolsets("coding"), [])

    def test_server_is_only_attached_to_selected_agent(self):
        self.save_server()
        self.assertEqual(self.service.build_toolsets("unity"), [])
        self.assertEqual(len(self.service.build_toolsets("coding")), 1)

    def test_disabled_server_builds_no_toolset(self):
        self.save_server(enabled=False)
        self.assertEqual(self.service.build_toolsets("coding"), [])

    def test_rejects_unknown_agent(self):
        with self.assertRaisesRegex(ValueError, "Unknown agents"):
            self.save_server(agent_ids=["admin"])

    def test_remote_plain_http_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must use HTTPS"):
            self.save_server(url="http://example.com/mcp")

    def test_local_plain_http_is_allowed(self):
        server = self.save_server(url="http://localhost:9999/mcp/")
        self.assertEqual(server["url"], "http://localhost:9999/mcp")

    def test_credentials_inside_url_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "credentials"):
            self.save_server(url="https://user:secret@example.com/mcp")

    def test_delete_removes_server(self):
        self.save_server()
        self.service.delete_server("docs")
        self.assertEqual(self.service.snapshot(), {"servers": []})

    def test_read_tools_are_allowed_and_mutating_tools_are_blocked(self):
        safe, _ = self.service._tool_is_read_only("search_docs", {})
        blocked, _ = self.service._tool_is_read_only("write_file", {})
        destructive, _ = self.service._tool_is_read_only(
            "search_docs", {"destructiveHint": True}
        )
        self.assertTrue(safe)
        self.assertFalse(blocked)
        self.assertFalse(destructive)


if __name__ == "__main__":
    unittest.main()
