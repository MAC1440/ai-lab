from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from services.task_context_service import (
    GeneratedChangeSet,
    ImplementationPlan,
)

BoundaryOperation = Literal["create", "update", "delete", "move"]


def _fallback_summary(operation: str, path: str) -> str:
    return f"{operation.capitalize()} {path}."


class ModelPlannedFile(BaseModel):
    """Tolerant model-facing plan item with strict safety validation."""

    model_config = ConfigDict(extra="ignore")

    path: str = Field(min_length=1, max_length=500)
    operation: BoundaryOperation
    reason: str = Field(default="", max_length=1000)
    destination_path: str | None = Field(default=None, max_length=500)

    def internal_payload(self) -> dict[str, Any]:
        destination = self.destination_path if self.operation == "move" else None
        return {
            "path": self.path,
            "operation": self.operation,
            "reason": self.reason.strip()
            or _fallback_summary(self.operation, self.path),
            "destination_path": destination,
        }

    @model_validator(mode="after")
    def validate_safety_fields(self):
        # This deliberately validates through the strict internal contract so
        # missing move destinations and unsafe paths still trigger an output
        # retry. Only harmless metadata is repaired.
        from services.task_context_service import PlannedFile

        PlannedFile.model_validate(self.internal_payload())
        return self


class ModelImplementationPlan(BaseModel):
    """Model-facing plan contract normalized into ImplementationPlan."""

    model_config = ConfigDict(extra="ignore")

    summary: str = Field(default="", max_length=2000)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    files: list[ModelPlannedFile] = Field(min_length=1, max_length=20)
    verification: list[str] = Field(default_factory=list, max_length=10)
    risks: list[str] = Field(default_factory=list, max_length=20)

    def internal_payload(self) -> dict[str, Any]:
        summary = self.summary.strip()
        if not summary:
            count = len(self.files)
            summary = f"Plan {count} file change{'s' if count != 1 else ''}."
        return {
            "summary": summary,
            "assumptions": self.assumptions,
            "files": [item.internal_payload() for item in self.files],
            "verification": self.verification,
            "risks": self.risks,
        }

    @model_validator(mode="after")
    def validate_strict_contract(self):
        ImplementationPlan.model_validate(self.internal_payload())
        return self


class ModelGeneratedFileChange(BaseModel):
    """Tolerant model-facing operation with strict payload validation."""

    model_config = ConfigDict(extra="ignore")

    path: str = Field(min_length=1, max_length=500)
    operation: BoundaryOperation
    summary: str = Field(default="", max_length=1000)
    content: str | None = Field(default=None, max_length=1_000_000)
    destination_path: str | None = Field(default=None, max_length=500)

    def internal_payload(self) -> dict[str, Any]:
        destination = self.destination_path if self.operation == "move" else None
        return {
            "path": self.path,
            "operation": self.operation,
            "summary": self.summary.strip()
            or _fallback_summary(self.operation, self.path),
            "content": self.content,
            "destination_path": destination,
        }

    @model_validator(mode="after")
    def validate_safety_fields(self):
        from services.task_context_service import GeneratedFileChange

        GeneratedFileChange.model_validate(self.internal_payload())
        return self


class ModelGeneratedChangeSet(BaseModel):
    """Model-facing change-set contract normalized into GeneratedChangeSet."""

    model_config = ConfigDict(extra="ignore")

    summary: str = Field(default="", max_length=2000)
    operations: list[ModelGeneratedFileChange] = Field(
        min_length=1,
        max_length=20,
    )

    def internal_payload(self) -> dict[str, Any]:
        summary = self.summary.strip()
        if not summary:
            count = len(self.operations)
            summary = f"Generate {count} file change{'s' if count != 1 else ''}."
        return {
            "summary": summary,
            "operations": [item.internal_payload() for item in self.operations],
        }

    @model_validator(mode="after")
    def validate_strict_contract(self):
        GeneratedChangeSet.model_validate(self.internal_payload())
        return self


def model_output_type(output_type: type[BaseModel]) -> type[BaseModel]:
    """Return the tolerant boundary contract for known task output types."""

    if output_type is ImplementationPlan:
        return ModelImplementationPlan
    if output_type is GeneratedChangeSet:
        return ModelGeneratedChangeSet
    return output_type


def normalize_model_output(
    output: BaseModel,
    output_type: type[BaseModel],
) -> tuple[BaseModel, list[str]]:
    """Convert model-facing output into the strict trusted task contract."""

    actions: list[str] = []
    if output_type is ImplementationPlan:
        boundary = ModelImplementationPlan.model_validate(output)
        if not boundary.summary.strip():
            actions.append("derived_plan_summary")
        for index, item in enumerate(boundary.files):
            if not item.reason.strip():
                actions.append(f"derived_file_reason:{index}")
            if item.operation != "move" and item.destination_path is not None:
                actions.append(f"discarded_non_move_destination:{index}")
        return (
            ImplementationPlan.model_validate(boundary.internal_payload()),
            actions,
        )

    if output_type is GeneratedChangeSet:
        boundary = ModelGeneratedChangeSet.model_validate(output)
        if not boundary.summary.strip():
            actions.append("derived_change_set_summary")
        for index, item in enumerate(boundary.operations):
            if not item.summary.strip():
                actions.append(f"derived_operation_summary:{index}")
            if item.operation != "move" and item.destination_path is not None:
                actions.append(f"discarded_non_move_destination:{index}")
        return (
            GeneratedChangeSet.model_validate(boundary.internal_payload()),
            actions,
        )

    return output_type.model_validate(output), actions
