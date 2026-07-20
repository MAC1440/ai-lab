import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from launcher.ai_lab_launcher import (
    LaunchError,
    find_project_root,
    request_ok,
    wait_for_url,
)


class LauncherTests(unittest.TestCase):
    def test_find_project_root_walks_up(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "backend").mkdir()
            (root / "frontend").mkdir()
            (root / "backend" / "main.py").touch()
            (root / "frontend" / "package.json").write_text("{}")
            nested = root / "launcher" / "nested"
            nested.mkdir(parents=True)
            self.assertEqual(find_project_root(nested), root)

    def test_find_project_root_rejects_unrelated_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(LaunchError):
                find_project_root(Path(folder))

    @patch("launcher.ai_lab_launcher.urllib.request.urlopen")
    def test_request_ok_accepts_success(self, urlopen):
        response = Mock(status=200)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        urlopen.return_value = response
        self.assertTrue(request_ok("http://127.0.0.1:8000/health"))

    @patch("launcher.ai_lab_launcher.request_ok", return_value=True)
    def test_wait_returns_immediately_when_ready(self, _request):
        self.assertTrue(wait_for_url("http://local", timeout=0.1))

    @patch("launcher.ai_lab_launcher.request_ok", return_value=False)
    def test_wait_stops_when_child_exits(self, _request):
        process = Mock()
        process.poll.return_value = 1
        self.assertFalse(
            wait_for_url("http://local", timeout=5, process=process)
        )


if __name__ == "__main__":
    unittest.main()
