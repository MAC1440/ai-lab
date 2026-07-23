from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from services.task_context_service import GeneratedChangeSet, GeneratedFileChange
from services.workspace_service import WorkspaceService


class SourceValidationError(ValueError):
    """Raised when generated source is unsafe to offer for approval."""

    def __init__(self, report: Dict[str, Any]) -> None:
        self.report = report
        errors = [
            f"{item['path']}: {item['message']}"
            for item in report.get("issues", [])
            if item.get("severity") == "error"
        ]
        super().__init__(
            "Generated source validation failed: " + "; ".join(errors[:8])
        )


@dataclass(frozen=True)
class _Issue:
    path: str
    severity: str
    code: str
    message: str
    line: Optional[int] = None
    column: Optional[int] = None

    def public(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "path": self.path,
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }
        if self.line is not None:
            result["line"] = self.line
        if self.column is not None:
            result["column"] = self.column
        return result


class SourceValidationService:
    """Validate generated text before a reviewable proposal is persisted.

    Python and JSON use their standard parsers. TypeScript/JavaScript uses the
    project's own TypeScript compiler when available. C# receives deterministic
    lexical and Unity filename/type checks here; the selected Unity or .NET
    verification profile remains the authoritative compiler check after apply.
    """

    _CSHARP_UNITY_BASES = {"MonoBehaviour", "ScriptableObject", "EditorWindow"}
    _TS_SUFFIXES = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}

    def __init__(
        self,
        workspace_service: WorkspaceService,
        *,
        typescript_timeout_seconds: int = 15,
    ) -> None:
        self.workspace_service = workspace_service
        self.typescript_timeout_seconds = typescript_timeout_seconds

    def validate(self, change_set: GeneratedChangeSet) -> Dict[str, Any]:
        issues: List[_Issue] = []
        checked: List[Dict[str, Any]] = []
        for operation in change_set.operations:
            if operation.operation not in {"create", "update"}:
                continue
            content = operation.content or ""
            suffix = Path(operation.path).suffix.lower()
            validators: List[str] = []
            if "\x00" in content:
                issues.append(
                    _Issue(
                        operation.path,
                        "error",
                        "nul_byte",
                        "Text source must not contain NUL bytes.",
                    )
                )
            if suffix in {".py", ".pyi"}:
                validators.append("python_ast")
                issues.extend(self._validate_python(operation, content))
            elif suffix == ".json":
                validators.append("json_parser")
                issues.extend(self._validate_json(operation, content))
            elif suffix == ".cs":
                validators.extend(("csharp_lexical", "unity_type_name"))
                issues.extend(self._validate_csharp(operation, content))
            elif suffix in self._TS_SUFFIXES:
                validators.append("typescript_parser")
                issues.extend(self._validate_typescript(operation, content))
            checked.append(
                {
                    "path": operation.path,
                    "operation": operation.operation,
                    "validators": validators,
                }
            )

        public_issues = [issue.public() for issue in issues]
        report = {
            "valid": not any(
                item["severity"] == "error" for item in public_issues
            ),
            "checked": checked,
            "issues": public_issues,
            "error_count": sum(
                item["severity"] == "error" for item in public_issues
            ),
            "warning_count": sum(
                item["severity"] == "warning" for item in public_issues
            ),
        }
        if not report["valid"]:
            raise SourceValidationError(report)
        return report

    @staticmethod
    def _validate_python(
        operation: GeneratedFileChange,
        content: str,
    ) -> Iterable[_Issue]:
        try:
            ast.parse(content, filename=operation.path, type_comments=True)
        except SyntaxError as error:
            yield _Issue(
                operation.path,
                "error",
                "python_syntax",
                error.msg,
                error.lineno,
                error.offset,
            )

    @staticmethod
    def _validate_json(
        operation: GeneratedFileChange,
        content: str,
    ) -> Iterable[_Issue]:
        try:
            json.loads(content)
        except json.JSONDecodeError as error:
            yield _Issue(
                operation.path,
                "error",
                "json_syntax",
                error.msg,
                error.lineno,
                error.colno,
            )

    def _validate_csharp(
        self,
        operation: GeneratedFileChange,
        content: str,
    ) -> Iterable[_Issue]:
        lexical_error = self._csharp_lexical_error(content)
        if lexical_error:
            yield _Issue(
                operation.path,
                "error",
                "csharp_lexical",
                lexical_error,
            )

        file_stem = Path(operation.path).stem
        declaration = re.compile(
            r"\bpublic\s+(?:abstract\s+|sealed\s+|partial\s+)*class\s+"
            r"(?P<name>[A-Za-z_]\w*)\s*(?::\s*(?P<bases>[^{]+))?\s*\{",
            re.MULTILINE,
        )
        for match in declaration.finditer(self._strip_csharp_comments(content)):
            raw_bases = match.group("bases") or ""
            bases = {
                part.strip().split("<", 1)[0].split(".")[-1]
                for part in raw_bases.split(",")
            }
            if bases.intersection(self._CSHARP_UNITY_BASES):
                class_name = match.group("name")
                if class_name != file_stem:
                    yield _Issue(
                        operation.path,
                        "error",
                        "unity_filename_type_mismatch",
                        (
                            f"Unity component class '{class_name}' must match "
                            f"the filename '{file_stem}.cs'."
                        ),
                    )

    def _validate_typescript(
        self,
        operation: GeneratedFileChange,
        content: str,
    ) -> Iterable[_Issue]:
        compiler = self._find_typescript_compiler(operation.path)
        node = shutil.which("node")
        if not compiler or not node:
            yield _Issue(
                operation.path,
                "warning",
                "typescript_parser_unavailable",
                (
                    "The project TypeScript compiler was not found; syntax will "
                    "be checked by the post-approval verification profile."
                ),
            )
            return

        script = r"""
const ts = require(process.argv[1]);
const fileName = process.argv[2];
let source = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", chunk => source += chunk);
process.stdin.on("end", () => {
  const target = ts.ScriptTarget.Latest;
  const kind = fileName.endsWith(".tsx") ? ts.ScriptKind.TSX
    : fileName.endsWith(".jsx") ? ts.ScriptKind.JSX
    : fileName.endsWith(".ts") ? ts.ScriptKind.TS
    : ts.ScriptKind.JS;
  const file = ts.createSourceFile(fileName, source, target, true, kind);
  const diagnostics = file.parseDiagnostics.map(d => {
    const pos = d.start == null ? {line: 0, character: 0}
      : file.getLineAndCharacterOfPosition(d.start);
    return {
      message: ts.flattenDiagnosticMessageText(d.messageText, "\n"),
      line: pos.line + 1,
      column: pos.character + 1
    };
  });
  process.stdout.write(JSON.stringify(diagnostics));
});
"""
        try:
            completed = subprocess.run(
                [node, "-e", script, str(compiler), operation.path],
                input=content,
                text=True,
                capture_output=True,
                timeout=self.typescript_timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            yield _Issue(
                operation.path,
                "warning",
                "typescript_parser_failed",
                f"TypeScript parser could not run: {error}",
            )
            return
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            yield _Issue(
                operation.path,
                "warning",
                "typescript_parser_failed",
                "TypeScript parser failed: " + detail[-800:],
            )
            return
        try:
            diagnostics = json.loads(completed.stdout or "[]")
        except json.JSONDecodeError:
            yield _Issue(
                operation.path,
                "warning",
                "typescript_parser_failed",
                "TypeScript parser returned an unreadable result.",
            )
            return
        for diagnostic in diagnostics:
            yield _Issue(
                operation.path,
                "error",
                "typescript_syntax",
                str(diagnostic.get("message") or "Invalid syntax"),
                int(diagnostic.get("line") or 1),
                int(diagnostic.get("column") or 1),
            )

    def _find_typescript_compiler(self, relative_path: str) -> Optional[Path]:
        root = self.workspace_service.get_workspace().resolve()
        target_parent = (root / relative_path).resolve().parent
        candidates = []
        current = target_parent
        while True:
            candidates.append(
                current / "node_modules" / "typescript" / "lib" / "typescript.js"
            )
            if current == root:
                break
            try:
                current.relative_to(root)
            except ValueError:
                break
            if current.parent == current:
                break
            current = current.parent
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    @classmethod
    def _csharp_lexical_error(cls, content: str) -> Optional[str]:
        cleaned = cls._strip_csharp_comments_and_literals(content)
        opening = {"{": "}", "(": ")", "[": "]"}
        closing = {value: key for key, value in opening.items()}
        stack: List[tuple[str, int]] = []
        line = 1
        for character in cleaned:
            if character == "\n":
                line += 1
            elif character in opening:
                stack.append((character, line))
            elif character in closing:
                if not stack or stack[-1][0] != closing[character]:
                    return f"Unexpected '{character}' near line {line}."
                stack.pop()
        if stack:
            character, opening_line = stack[-1]
            return f"Unclosed '{character}' opened near line {opening_line}."
        return None

    @staticmethod
    def _strip_csharp_comments(content: str) -> str:
        return re.sub(
            r"//[^\n]*|/\*.*?\*/",
            lambda match: "\n" * match.group(0).count("\n"),
            content,
            flags=re.DOTALL,
        )

    @staticmethod
    def _strip_csharp_comments_and_literals(content: str) -> str:
        pattern = re.compile(
            r'//[^\n]*|/\*.*?\*/|@"(?:""|[^"])*"|'
            r'\$?"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])\'',
            re.DOTALL,
        )
        return pattern.sub(
            lambda match: "\n" * match.group(0).count("\n"),
            content,
        )
