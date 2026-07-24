import unittest

from pydantic import ValidationError

from services.task_context_service import (
    GeneratedChangeSet,
    ImplementationPlan,
)
from services.task_model_output_adapter import (
    ModelGeneratedChangeSet,
    ModelImplementationPlan,
    model_output_type,
    normalize_model_output,
)


class TaskModelOutputAdapterTests(unittest.TestCase):
    def test_normalizes_granite_plan_destination_on_non_move(self):
        boundary = ModelImplementationPlan.model_validate(
            {
                "summary": "Implement discount behavior.",
                "files": [
                    {
                        "path": "src/pricing.py",
                        "operation": "update",
                        "reason": "Apply percentage discount.",
                        "destination_path": "/src/pricing.py",
                    }
                ],
                "verification": ["python-tests"],
            }
        )

        output, actions = normalize_model_output(
            boundary,
            ImplementationPlan,
        )

        self.assertIsInstance(output, ImplementationPlan)
        self.assertIsNone(output.files[0].destination_path)
        self.assertEqual(
            actions,
            ["discarded_non_move_destination:0"],
        )

    def test_normalizes_granite_missing_operation_summaries(self):
        boundary = ModelGeneratedChangeSet.model_validate(
            {
                "summary": "Implement greeting.",
                "operations": [
                    {
                        "path": "src/existing.py",
                        "operation": "update",
                        "content": "from src.greeting import greet\n",
                    },
                    {
                        "path": "src/greeting.py",
                        "operation": "create",
                        "content": (
                            "def greet(name: str) -> str:\n"
                            '    return f"Hello, {name}"\n'
                        ),
                    },
                ],
            }
        )

        output, actions = normalize_model_output(
            boundary,
            GeneratedChangeSet,
        )

        self.assertIsInstance(output, GeneratedChangeSet)
        self.assertEqual(
            [item.summary for item in output.operations],
            ["Update src/existing.py.", "Create src/greeting.py."],
        )
        self.assertEqual(
            actions,
            [
                "derived_operation_summary:0",
                "derived_operation_summary:1",
            ],
        )

    def test_derives_nonessential_container_and_reason_metadata(self):
        boundary = ModelImplementationPlan.model_validate(
            {
                "files": [
                    {
                        "path": "src/example.py",
                        "operation": "create",
                    }
                ]
            }
        )

        output, actions = normalize_model_output(
            boundary,
            ImplementationPlan,
        )

        self.assertEqual(output.summary, "Plan 1 file change.")
        self.assertEqual(output.files[0].reason, "Create src/example.py.")
        self.assertEqual(
            actions,
            ["derived_plan_summary", "derived_file_reason:0"],
        )

    def test_keeps_safety_critical_operation_fields_required(self):
        with self.assertRaises(ValidationError) as raised:
            ModelGeneratedChangeSet.model_validate(
                {
                    "operations": [
                        {
                            "content": "def add(a, b): return a + b\n",
                        }
                    ]
                }
            )

        message = str(raised.exception)
        self.assertIn("path", message)
        self.assertIn("operation", message)

    def test_keeps_create_and_update_content_required(self):
        with self.assertRaisesRegex(
            ValidationError,
            "complete file content",
        ):
            ModelGeneratedChangeSet.model_validate(
                {
                    "operations": [
                        {
                            "path": "src/example.py",
                            "operation": "update",
                        }
                    ]
                }
            )

    def test_keeps_move_destination_required(self):
        with self.assertRaisesRegex(
            ValidationError,
            "Move operations require destination_path",
        ):
            ModelImplementationPlan.model_validate(
                {
                    "files": [
                        {
                            "path": "src/old.py",
                            "operation": "move",
                            "reason": "Rename the module.",
                        }
                    ]
                }
            )

    def test_only_known_task_contracts_use_boundary_types(self):
        self.assertIs(
            model_output_type(ImplementationPlan),
            ModelImplementationPlan,
        )
        self.assertIs(
            model_output_type(GeneratedChangeSet),
            ModelGeneratedChangeSet,
        )

    def test_strict_internal_contract_remains_unchanged(self):
        with self.assertRaisesRegex(
            ValidationError,
            "destination_path is only valid for move operations",
        ):
            ImplementationPlan.model_validate(
                {
                    "summary": "Unsafe direct plan.",
                    "files": [
                        {
                            "path": "src/example.py",
                            "operation": "update",
                            "reason": "Change it.",
                            "destination_path": "src/other.py",
                        }
                    ],
                }
            )

        with self.assertRaisesRegex(ValidationError, "summary"):
            GeneratedChangeSet.model_validate(
                {
                    "summary": "Direct strict change set.",
                    "operations": [
                        {
                            "path": "src/example.py",
                            "operation": "update",
                            "content": "value = 1\n",
                        }
                    ],
                }
            )


if __name__ == "__main__":
    unittest.main()
