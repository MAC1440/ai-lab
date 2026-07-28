import json
import os
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from launcher.ai_lab_launcher import (
    LaunchError,
    ServiceProbe,
    cleanup_old_logs,
    create_diagnostics_bundle,
    find_project_root,
    identity_matches,
    main,
    read_build_marker,
    request_ok,
    runtime_identity,
    source_fingerprint,
    status_report,
    validate_installation,
    write_build_marker,
)


class LauncherTests(unittest.TestCase):
    def make_root(self, folder: str) -> Path:
        root = Path(folder)
        (root / "backend").mkdir(exist_ok=True)
        (root / "frontend").mkdir(exist_ok=True)
        (root / "launcher").mkdir(exist_ok=True)
        (root / "backend" / "main.py").write_text(
            "APP = 'backend'\n",
            encoding="utf-8",
        )
        (root / "frontend" / "package.json").write_text(
            "{}\n",
            encoding="utf-8",
        )
        (root / "launcher" / "ai_lab_launcher.py").write_text(
            "APP = 'launcher'\n",
            encoding="utf-8",
        )
        return root

    def test_find_project_root_walks_up(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.make_root(folder)
            nested = root / "launcher" / "nested"
            nested.mkdir(parents=True)
            self.assertEqual(find_project_root(nested), root)

    def test_find_project_root_rejects_unrelated_folder(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            self.assertRaises(LaunchError),
        ):
            find_project_root(Path(folder))

    @patch("launcher.ai_lab_launcher.urllib.request.urlopen")
    def test_request_ok_accepts_success(self, urlopen):
        response = Mock(status=200)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        urlopen.return_value = response
        self.assertTrue(request_ok("http://127.0.0.1:8000/health"))

    def test_source_fingerprint_changes_with_runtime_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.make_root(folder)
            before = source_fingerprint(root)

            (root / "backend" / "main.py").write_text(
                "APP = 'changed'\n",
                encoding="utf-8",
            )

            self.assertNotEqual(before, source_fingerprint(root))

    def test_identity_requires_service_checkout_and_source_match(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.make_root(folder)
            expected = runtime_identity(root)
            valid = ServiceProbe(
                reachable=True,
                status=200,
                payload={
                    "status": "ok",
                    "service": "ai-lab-backend",
                    "checkout_id": expected["checkout_id"],
                    "source_fingerprint": expected["source_fingerprint"],
                },
            )
            stale = ServiceProbe(
                reachable=True,
                status=200,
                payload={**valid.payload, "source_fingerprint": "stale"},
            )

            self.assertTrue(
                identity_matches(
                    valid,
                    service="ai-lab-backend",
                    expected=expected,
                )
            )
            self.assertFalse(
                identity_matches(
                    stale,
                    service="ai-lab-backend",
                    expected=expected,
                )
            )

    def test_production_validation_rejects_stale_build(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.make_root(folder)
            python = root / "backend" / ".venv" / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.touch()
            (root / "frontend" / "node_modules").mkdir()
            build = root / "frontend" / ".next"
            build.mkdir()
            (build / "BUILD_ID").write_text("build\n", encoding="utf-8")

            with patch(
                "launcher.ai_lab_launcher.npm_command",
                return_value="npm",
            ):
                write_build_marker(root)
                validate_installation(root, "production")

                (root / "backend" / "main.py").write_text(
                    "APP = 'new source'\n",
                    encoding="utf-8",
                )

                with self.assertRaisesRegex(LaunchError, "stale"):
                    validate_installation(root, "production")

    def test_write_build_marker_records_current_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.make_root(folder)
            build = root / "frontend" / ".next"
            build.mkdir()
            (build / "BUILD_ID").write_text("build\n", encoding="utf-8")

            marker = write_build_marker(root)

            self.assertEqual(
                marker["source_fingerprint"],
                source_fingerprint(root),
            )
            self.assertEqual(read_build_marker(root), marker)

    def test_cleanup_old_logs_keeps_recent_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.make_root(folder)
            logs = root / "backend" / "data" / "logs"
            logs.mkdir(parents=True)
            old = logs / "old.log"
            recent = logs / "recent.log"
            old.write_text("old", encoding="utf-8")
            recent.write_text("recent", encoding="utf-8")
            now = datetime.now(timezone.utc)
            old_time = (now - timedelta(days=20)).timestamp()
            os.utime(old, (old_time, old_time))

            removed = cleanup_old_logs(root, now=now)

            self.assertEqual(removed, [old])
            self.assertFalse(old.exists())
            self.assertTrue(recent.exists())

    def test_diagnostics_excludes_log_contents(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.make_root(folder)
            logs = root / "backend" / "data" / "logs"
            logs.mkdir(parents=True)
            (logs / "backend.log").write_text(
                "SECRET_PROMPT_CONTENT",
                encoding="utf-8",
            )

            with (
                patch(
                    "launcher.ai_lab_launcher.probe_json",
                    return_value=ServiceProbe(False, None, None),
                ),
                patch(
                    "launcher.ai_lab_launcher.request_ok",
                    return_value=False,
                ),
                patch(
                    "launcher.ai_lab_launcher._command_version",
                    return_value=None,
                ),
                patch(
                    "launcher.ai_lab_launcher.npm_command",
                    return_value="npm",
                ),
            ):
                bundle = create_diagnostics_bundle(root)

            with zipfile.ZipFile(bundle) as archive:
                names = set(archive.namelist())
                report = json.loads(archive.read("diagnostics.json"))
                combined = b"\n".join(
                    archive.read(name) for name in archive.namelist()
                )

            self.assertEqual(
                names,
                {"diagnostics.json", "README.txt"},
            )
            self.assertEqual(report["logs"][0]["name"], "backend.log")
            self.assertNotIn(b"SECRET_PROMPT_CONTENT", combined)

    def test_status_marks_abandoned_running_state_as_stale(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.make_root(folder)
            state_path = root / "backend" / "data" / "launcher-state.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                json.dumps({"status": "running"}),
                encoding="utf-8",
            )

            with (
                patch(
                    "launcher.ai_lab_launcher.probe_json",
                    return_value=ServiceProbe(False, None, None),
                ),
                patch(
                    "launcher.ai_lab_launcher.request_ok",
                    return_value=False,
                ),
            ):
                report = status_report(root)

            self.assertEqual(
                report["launcher_state"]["effective_status"],
                "stale",
            )

    def test_keyboard_interrupt_writes_stopped_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.make_root(folder)

            with (
                patch("launcher.ai_lab_launcher.validate_installation"),
                patch("launcher.ai_lab_launcher.cleanup_old_logs"),
                patch("launcher.ai_lab_launcher.report_ollama"),
                patch("launcher.ai_lab_launcher.ensure_backend"),
                patch("launcher.ai_lab_launcher.ensure_frontend"),
                patch(
                    "launcher.ai_lab_launcher.time.sleep",
                    side_effect=KeyboardInterrupt,
                ),
            ):
                exit_code = main(
                    [
                        "--root",
                        str(root),
                        "--no-browser",
                    ]
                )

            state = json.loads(
                (
                    root / "backend" / "data" / "launcher-state.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(state["status"], "stopped")
            self.assertIsNone(state["error"])

    def test_start_failure_writes_error_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.make_root(folder)

            with (
                patch("launcher.ai_lab_launcher.validate_installation"),
                patch("launcher.ai_lab_launcher.cleanup_old_logs"),
                patch("launcher.ai_lab_launcher.report_ollama"),
                patch(
                    "launcher.ai_lab_launcher.ensure_backend",
                    side_effect=LaunchError("backend failed"),
                ),
            ):
                exit_code = main(
                    [
                        "--root",
                        str(root),
                        "--no-browser",
                    ]
                )

            state = json.loads(
                (
                    root / "backend" / "data" / "launcher-state.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(exit_code, 1)
            self.assertEqual(state["status"], "error")
            self.assertEqual(state["error"], "backend failed")


if __name__ == "__main__":
    unittest.main()
