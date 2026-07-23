import tempfile
import unittest
from pathlib import Path

from services.source_validation_service import (
    SourceValidationError,
    SourceValidationService,
)
from services.task_context_service import GeneratedChangeSet


class TemporaryWorkspaceService:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def get_workspace(self) -> Path:
        return self.root


class SourceValidationServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.service = SourceValidationService(
            TemporaryWorkspaceService(self.root)
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def change_set(self, path: str, content: str) -> GeneratedChangeSet:
        return GeneratedChangeSet.model_validate(
            {
                "summary": "Validate generated source.",
                "operations": [
                    {
                        "path": path,
                        "operation": "create",
                        "summary": "Create source.",
                        "content": content,
                    }
                ],
            }
        )

    def test_rejects_python_syntax_before_proposal(self):
        with self.assertRaises(SourceValidationError) as raised:
            self.service.validate(
                self.change_set("src/broken.py", "def broken(:\n    pass\n")
            )

        self.assertEqual(
            raised.exception.report["issues"][0]["code"],
            "python_syntax",
        )

    def test_rejects_invalid_json(self):
        with self.assertRaises(SourceValidationError):
            self.service.validate(
                self.change_set("config.json", '{"missing": }')
            )

    def test_rejects_unbalanced_csharp(self):
        with self.assertRaisesRegex(SourceValidationError, "Unclosed"):
            self.service.validate(
                self.change_set(
                    "Assets/Health.cs",
                    "public class Health : MonoBehaviour {\n",
                )
            )

    def test_rejects_unity_component_filename_mismatch(self):
        with self.assertRaisesRegex(SourceValidationError, "must match"):
            self.service.validate(
                self.change_set(
                    "Assets/Health.cs",
                    "public class PlayerHealth : MonoBehaviour {}\n",
                )
            )

    def test_missing_typescript_compiler_is_visible_warning(self):
        report = self.service.validate(
            self.change_set(
                "src/example.ts",
                "export const value: number = 1;\n",
            )
        )

        self.assertTrue(report["valid"])
        self.assertEqual(report["warning_count"], 1)
        self.assertEqual(
            report["issues"][0]["code"],
            "typescript_parser_unavailable",
        )


if __name__ == "__main__":
    unittest.main()
