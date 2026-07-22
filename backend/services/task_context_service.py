from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from services.workspace_service import WorkspaceService


PlanOperation = Literal["create", "update", "delete", "move"]
TEXT_SUFFIXES = {
    ".cs", ".css", ".html", ".ini", ".js", ".json", ".jsx", ".md",
    ".mjs", ".py", ".pyi", ".toml", ".ts", ".tsx", ".txt", ".xml",
    ".yaml", ".yml",
}
BLOCKED_PARTS = {
    ".git", ".next", ".venv", "Library", "Logs", "Temp", "obj",
    "node_modules", "dist", "build",
}


class PlannedFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=500)
    operation: PlanOperation
    reason: str = Field(min_length=1, max_length=1000)
    destination_path: Optional[str] = Field(default=None, max_length=500)

    @field_validator("path", "destination_path")
    @classmethod
    def normalize_path(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        clean = value.strip().replace("\\", "/").lstrip("./")
        if not clean or clean.startswith("/") or ".." in Path(clean).parts:
            raise ValueError("Path must be workspace-relative")
        if any(part in BLOCKED_PARTS for part in Path(clean).parts):
            raise ValueError("Path targets a generated or protected directory")
        return clean

    @model_validator(mode="after")
    def validate_move(self):
        if self.operation == "move" and not self.destination_path:
            raise ValueError("Move operations require destination_path")
        if self.operation != "move" and self.destination_path is not None:
            raise ValueError("destination_path is only valid for move operations")
        return self


class ImplementationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=2000)
    assumptions: List[str] = Field(default_factory=list, max_length=20)
    files: List[PlannedFile] = Field(min_length=1, max_length=20)
    verification: List[str] = Field(default_factory=list, max_length=10)
    risks: List[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def reject_conflicts(self):
        paths: set[str] = set()
        for item in self.files:
            for path in (item.path, item.destination_path):
                if path is None:
                    continue
                key = path.casefold()
                if key in paths:
                    raise ValueError(f"Duplicate or conflicting plan path: {path}")
                paths.add(key)
        return self


class TaskContextService:
    """Compile exact, reproducible project files for one generation stage."""

    def __init__(
        self,
        workspace_service: WorkspaceService,
        *,
        max_total_bytes: int = 240_000,
        max_file_bytes: int = 80_000,
    ) -> None:
        if max_total_bytes < 1 or max_file_bytes < 1:
            raise ValueError("Context byte limits must be positive")
        self.workspace_service = workspace_service
        self.max_total_bytes = max_total_bytes
        self.max_file_bytes = max_file_bytes

    def compile(self, plan: ImplementationPlan) -> Dict[str, Any]:
        root = self.workspace_service.get_workspace().resolve()
        files: List[Dict[str, Any]] = []
        omitted: List[Dict[str, str]] = []
        used = 0

        requested = self._paths_to_read(plan.files)
        for relative in requested:
            target = self._resolve(root, relative)
            if not target.exists():
                omitted.append({"path": relative, "reason": "not_found"})
                continue
            if not target.is_file():
                omitted.append({"path": relative, "reason": "not_a_file"})
                continue
            if target.suffix.lower() not in TEXT_SUFFIXES:
                omitted.append({"path": relative, "reason": "unsupported_type"})
                continue
            raw = target.read_bytes()
            if len(raw) > self.max_file_bytes:
                omitted.append({"path": relative, "reason": "file_too_large"})
                continue
            if used + len(raw) > self.max_total_bytes:
                omitted.append({"path": relative, "reason": "budget_exhausted"})
                continue
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                omitted.append({"path": relative, "reason": "not_utf8"})
                continue
            files.append(
                {
                    "path": relative,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "bytes": len(raw),
                    "content": content,
                }
            )
            used += len(raw)

        missing_required = [
            item["path"]
            for item in omitted
            if item["reason"] in {"not_found", "not_a_file"}
        ]
        return {
            "version": 1,
            "workspace": str(root),
            "files": files,
            "omitted": omitted,
            "bytes": used,
            "max_bytes": self.max_total_bytes,
            "complete": not missing_required,
            "missing_required": missing_required,
        }

    @staticmethod
    def _paths_to_read(files: Iterable[PlannedFile]) -> List[str]:
        result: List[str] = []
        for item in files:
            if item.operation in {"update", "delete", "move"} and item.path not in result:
                result.append(item.path)
        return result

    @staticmethod
    def _resolve(root: Path, relative: str) -> Path:
        target = (root / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError as error:
            raise ValueError(f"Path escapes the workspace: {relative}") from error
        return target
