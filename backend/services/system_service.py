from __future__ import annotations

import io
import json
import os
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx


class SystemService:
    """Run local readiness checks and create secret-free application backups."""

    def __init__(
        self,
        *,
        workspace_service: Any,
        provider_settings_service: Any,
        mcp_service: Any,
        agent_ids: list[str],
        database_paths: dict[str, Path],
        config_paths: dict[str, Path],
        data_directory: Path,
    ) -> None:
        self.workspace_service = workspace_service
        self.provider_settings_service = provider_settings_service
        self.mcp_service = mcp_service
        self.agent_ids = agent_ids
        self.database_paths = database_paths
        self.config_paths = config_paths
        self.data_directory = data_directory

    def diagnostics(self) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        checks.append(self._python_check())
        checks.append(self._storage_check())
        checks.append(self._workspace_check())
        checks.extend(self._database_checks())
        checks.extend(self._ollama_checks())
        checks.extend(self._security_checks())

        summary = {
            "passed": sum(item["status"] == "pass" for item in checks),
            "warnings": sum(item["status"] == "warning" for item in checks),
            "failed": sum(item["status"] == "fail" for item in checks),
        }
        overall = (
            "blocked" if summary["failed"] else
            "attention" if summary["warnings"] else "ready"
        )
        return {
            "status": overall,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "checks": checks,
        }

    def create_backup(self) -> tuple[str, bytes]:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        output = io.BytesIO()
        manifest: dict[str, Any] = {
            "format": "ai-lab-backup",
            "version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "contains_workspace_files": False,
            "contains_api_keys": False,
            "files": [],
        }

        with tempfile.TemporaryDirectory(prefix="ai-lab-backup-") as folder:
            temporary_root = Path(folder)
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, path in self.config_paths.items():
                    if not path.exists():
                        continue
                    destination = f"config/{name}.json"
                    archive.writestr(destination, path.read_bytes())
                    manifest["files"].append(destination)

                for name, path in self.database_paths.items():
                    if not path.exists():
                        continue
                    copied = temporary_root / f"{name}.sqlite3"
                    source = sqlite3.connect(path, timeout=5)
                    destination_connection = sqlite3.connect(copied)
                    try:
                        source.backup(destination_connection)
                    finally:
                        destination_connection.close()
                        source.close()
                    destination = f"databases/{name}.sqlite3"
                    archive.write(copied, destination)
                    manifest["files"].append(destination)

                archive.writestr(
                    "manifest.json",
                    json.dumps(manifest, indent=2) + "\n",
                )
        return f"ai-lab-backup-{timestamp}.zip", output.getvalue()

    @staticmethod
    def _check(
        check_id: str,
        name: str,
        status: str,
        message: str,
        action: str | None = None,
    ) -> dict[str, Any]:
        return {
            "id": check_id,
            "name": name,
            "status": status,
            "message": message,
            "action": action,
        }

    def _python_check(self) -> dict[str, Any]:
        version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        supported = (3, 11) <= sys.version_info[:2] <= (3, 13)
        return self._check(
            "python", "Python runtime", "pass" if supported else "warning",
            f"Python {version} is running.",
            None if supported else "Python 3.11 or 3.12 is the safest choice for AI Lab dependencies.",
        )

    def _storage_check(self) -> dict[str, Any]:
        try:
            self.data_directory.mkdir(parents=True, exist_ok=True)
            probe = self.data_directory / ".write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return self._check("storage", "Application storage", "pass", f"Writable: {self.data_directory}")
        except OSError as error:
            return self._check("storage", "Application storage", "fail", str(error), "Give the backend write access to its data directory.")

    def _workspace_check(self) -> dict[str, Any]:
        raw = self.workspace_service.get_workspace_info().get("workspace")
        if not raw:
            return self._check("workspace", "Selected workspace", "warning", "No workspace is selected.", "Select a workspace before using coding agents.")
        path = Path(raw)
        if not path.exists() or not path.is_dir():
            return self._check("workspace", "Selected workspace", "fail", f"Workspace is unavailable: {path}", "Select an existing folder.")
        return self._check("workspace", "Selected workspace", "pass", str(path))

    def _database_checks(self) -> list[dict[str, Any]]:
        results = []
        for name, path in self.database_paths.items():
            if not path.exists():
                results.append(self._check(f"db-{name}", f"{name.title()} database", "warning", "Not created yet; this is normal until the feature is used."))
                continue
            try:
                connection = sqlite3.connect(path, timeout=3)
                try:
                    result = connection.execute("PRAGMA quick_check").fetchone()
                finally:
                    connection.close()
                healthy = bool(result and result[0] == "ok")
                results.append(self._check(f"db-{name}", f"{name.title()} database", "pass" if healthy else "fail", "Integrity check passed." if healthy else f"Integrity result: {result}"))
            except sqlite3.Error as error:
                results.append(self._check(f"db-{name}", f"{name.title()} database", "fail", str(error), "Create a backup before repairing or replacing this database."))
        return results

    def _ollama_checks(self) -> list[dict[str, Any]]:
        try:
            provider = self.provider_settings_service.get_provider("ollama")
            response = httpx.get(f"{provider['base_url']}/api/tags", timeout=4)
            response.raise_for_status()
            installed = {
                item.get("name") or item.get("model")
                for item in response.json().get("models", [])
            }
            installed.discard(None)
        except Exception as error:
            return [self._check("ollama", "Ollama", "fail", f"Cannot reach Ollama: {error}", "Start Ollama and verify its base URL in Models settings.")]

        assigned = {
            self.provider_settings_service.resolve_agent(agent_id)["model"]
            for agent_id in self.agent_ids
            if self.provider_settings_service.resolve_agent(agent_id)["provider_id"] == "ollama"
        }
        missing = sorted(assigned - installed)
        return [
            self._check("ollama", "Ollama", "pass", f"Connected; found {len(installed)} installed model(s)."),
            self._check(
                "assigned-models", "Assigned Ollama models",
                "warning" if missing else "pass",
                "Missing: " + ", ".join(missing) if missing else "Every assigned Ollama model is installed.",
                "Pull the missing model or change the agent assignment." if missing else None,
            ),
        ]

    def _security_checks(self) -> list[dict[str, Any]]:
        host = os.getenv("HOST", "127.0.0.1").strip()
        local_host = host in {"127.0.0.1", "localhost", "::1"}
        results = [self._check(
            "network-binding", "Backend network binding",
            "pass" if local_host else "warning",
            f"HOST={host}",
            None if local_host else "For personal local use, set HOST=127.0.0.1 so the API is not exposed to your LAN.",
        )]
        remote = []
        for server in self.mcp_service.snapshot().get("servers", []):
            hostname = (urlparse(server.get("url", "")).hostname or "").lower()
            if server.get("enabled") and hostname not in {"localhost", "127.0.0.1", "::1"}:
                remote.append(server.get("name", server.get("id", "unknown")))
        results.append(self._check(
            "remote-mcp", "Remote MCP access", "warning" if remote else "pass",
            "Enabled remote servers: " + ", ".join(remote) if remote else "No remote MCP server is enabled.",
            "Only enable remote servers you trust." if remote else None,
        ))
        return results
