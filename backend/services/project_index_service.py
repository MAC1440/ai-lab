from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sqlite3
import time
from collections import defaultdict
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from pathspec import GitIgnoreSpec, PathSpec

from services.project_detection_service import IGNORED_DIRECTORIES
from services.workspace_service import WorkspaceService

INDEXED_SUFFIXES = {
    ".cs",
    ".css",
    ".html",
    ".js",
    ".jsx",
    ".mjs",
    ".py",
    ".pyi",
    ".ts",
    ".tsx",
}
MANIFEST_NAMES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "tsconfig.json",
    "projectversion.txt",
    "manifest.json",
}
TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,63}")
CAMEL_BOUNDARY_PATTERN = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
JS_IMPORT_PATTERN = re.compile(
    r"(?:import|export)\s+(?:[^;]*?\s+from\s+)?[\"']([^\"']+)[\"']"
    r"|require\s*\(\s*[\"']([^\"']+)[\"']\s*\)"
    r"|import\s*\(\s*[\"']([^\"']+)[\"']\s*\)",
)
JS_SYMBOL_PATTERN = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?"
    r"(?:(class|interface|type|enum|function)\s+([A-Za-z_$][\w$]*)"
    r"|(?:const|let|var)\s+([A-Za-z_$][\w$]*))",
    re.MULTILINE,
)
CS_SYMBOL_PATTERN = re.compile(
    r"^\s*(?:(?:public|private|protected|internal|static|sealed|abstract|"
    r"partial|virtual|override|async|readonly)\s+)*"
    r"(class|struct|interface|enum|record|namespace)\s+([A-Za-z_][\w.]*)",
    re.MULTILINE,
)
CS_USING_PATTERN = re.compile(
    r"^\s*using\s+(?:[A-Za-z_][\w]*\s*=\s*)?([A-Za-z_][\w.]*)\s*;",
    re.MULTILINE,
)
STOP_WORDS = {
    "add",
    "and",
    "app",
    "build",
    "change",
    "create",
    "fix",
    "for",
    "from",
    "implement",
    "into",
    "make",
    "new",
    "page",
    "project",
    "the",
    "this",
    "update",
    "use",
    "with",
}


class ProjectIndexService:
    """Persist a compact source index and rank likely task context files.

    The database deliberately stores paths, hashes, symbols, and dependency
    references, but never full source content. ProjectContextService still
    reads current files from the selected workspace before model inference.
    """

    SCHEMA_VERSION = 1

    def __init__(
        self,
        workspace_service: WorkspaceService,
        database_path: Path,
        *,
        max_files: int = 20_000,
        max_file_bytes: int = 1_500_000,
    ) -> None:
        if max_files < 1 or max_file_bytes < 1:
            raise ValueError("Project index limits must be positive")
        self.workspace_service = workspace_service
        self.database_path = Path(database_path)
        self.max_files = max_files
        self.max_file_bytes = max_file_bytes
        self._lock = RLock()
        self._initialize()

    def status(self) -> dict[str, Any]:
        workspace = self.workspace_service.get_workspace().resolve()
        workspace_key = self._workspace_key(workspace)
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT workspace, indexed_at, duration_ms, file_count,
                       symbol_count, reference_count, scan_truncated,
                       last_error
                FROM workspaces
                WHERE workspace_key = ?
                """,
                (workspace_key,),
            ).fetchone()
        if row is None:
            return {
                "status": "not_indexed",
                "workspace": str(workspace),
                "indexed_at": None,
                "duration_ms": None,
                "file_count": 0,
                "symbol_count": 0,
                "reference_count": 0,
                "scan_truncated": False,
                "last_error": None,
                "schema_version": self.SCHEMA_VERSION,
            }
        return {
            "status": "ready" if not row["last_error"] else "attention",
            "workspace": row["workspace"],
            "indexed_at": row["indexed_at"],
            "duration_ms": row["duration_ms"],
            "file_count": row["file_count"],
            "symbol_count": row["symbol_count"],
            "reference_count": row["reference_count"],
            "scan_truncated": bool(row["scan_truncated"]),
            "last_error": row["last_error"],
            "schema_version": self.SCHEMA_VERSION,
        }

    def refresh(self, *, rebuild: bool = False) -> dict[str, Any]:
        started = time.monotonic()
        workspace = self.workspace_service.get_workspace().resolve()
        workspace_key = self._workspace_key(workspace)

        with self._lock:
            try:
                discovered, scan_truncated = self._discover(workspace)
                with self._connection() as connection:
                    existing = {
                        row["path"]: (row["size"], row["mtime_ns"])
                        for row in connection.execute(
                            """
                            SELECT path, size, mtime_ns
                            FROM files
                            WHERE workspace_key = ?
                            """,
                            (workspace_key,),
                        )
                    }
                    removed = sorted(set(existing) - set(discovered))
                    changed = sorted(
                        path
                        for path, metadata in discovered.items()
                        if rebuild or existing.get(path) != metadata
                    )
                    unchanged_count = len(discovered) - len(changed)

                    connection.execute("BEGIN IMMEDIATE")
                    if rebuild:
                        self._delete_workspace_rows(connection, workspace_key)
                    else:
                        for relative in removed:
                            self._delete_file_rows(connection, workspace_key, relative)

                    unreadable = 0
                    for relative in changed:
                        target = workspace / relative
                        size, mtime_ns = discovered[relative]
                        try:
                            raw = target.read_bytes()
                            content = raw.decode("utf-8")
                        except (OSError, UnicodeDecodeError):
                            unreadable += 1
                            self._delete_file_rows(connection, workspace_key, relative)
                            continue
                        language = self._language_for(target)
                        symbols, references = self._parse(
                            content=content,
                            language=language,
                        )
                        self._replace_file(
                            connection,
                            workspace_key=workspace_key,
                            path=relative,
                            size=size,
                            mtime_ns=mtime_ns,
                            sha256=hashlib.sha256(raw).hexdigest(),
                            language=language,
                            symbols=symbols,
                            references=references,
                        )

                    self._resolve_edges(
                        connection,
                        workspace_key=workspace_key,
                    )
                    counts = connection.execute(
                        """
                        SELECT
                            (SELECT COUNT(*) FROM files
                             WHERE workspace_key = ?) AS file_count,
                            (SELECT COUNT(*) FROM symbols
                             WHERE workspace_key = ?) AS symbol_count,
                            (SELECT COUNT(*) FROM refs
                             WHERE workspace_key = ?) AS reference_count
                        """,
                        (workspace_key, workspace_key, workspace_key),
                    ).fetchone()
                    duration_ms = round((time.monotonic() - started) * 1000)
                    indexed_at = self._utc_now()
                    connection.execute(
                        """
                        INSERT INTO workspaces (
                            workspace_key, workspace, schema_version,
                            indexed_at, duration_ms, file_count, symbol_count,
                            reference_count, scan_truncated, last_error
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                        ON CONFLICT(workspace_key) DO UPDATE SET
                            workspace = excluded.workspace,
                            schema_version = excluded.schema_version,
                            indexed_at = excluded.indexed_at,
                            duration_ms = excluded.duration_ms,
                            file_count = excluded.file_count,
                            symbol_count = excluded.symbol_count,
                            reference_count = excluded.reference_count,
                            scan_truncated = excluded.scan_truncated,
                            last_error = NULL
                        """,
                        (
                            workspace_key,
                            str(workspace),
                            self.SCHEMA_VERSION,
                            indexed_at,
                            duration_ms,
                            counts["file_count"],
                            counts["symbol_count"],
                            counts["reference_count"],
                            int(scan_truncated),
                        ),
                    )
                    connection.commit()
                return {
                    **self.status(),
                    "refresh": {
                        "rebuild": rebuild,
                        "changed_files": len(changed),
                        "unchanged_files": unchanged_count,
                        "removed_files": len(removed),
                        "unreadable_files": unreadable,
                    },
                }
            except Exception as error:
                self._record_error(
                    workspace_key=workspace_key,
                    workspace=workspace,
                    error=str(error),
                    duration_ms=round((time.monotonic() - started) * 1000),
                )
                raise

    def query(
        self,
        text: str,
        *,
        limit: int = 8,
        project_root: str | None = None,
        refresh: bool = True,
    ) -> dict[str, Any]:
        if limit < 1 or limit > 50:
            raise ValueError("Project index query limit must be between 1 and 50")
        workspace = self.workspace_service.get_workspace().resolve()
        workspace_key = self._workspace_key(workspace)
        refresh_result = self.refresh() if refresh else None
        tokens = self._query_tokens(text)
        root_prefix = self._normalize_project_root(project_root)

        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT f.path, f.language,
                       COALESCE(GROUP_CONCAT(s.name, char(31)), '') AS symbols
                FROM files AS f
                LEFT JOIN symbols AS s
                  ON s.workspace_key = f.workspace_key AND s.path = f.path
                WHERE f.workspace_key = ?
                GROUP BY f.path, f.language
                ORDER BY f.path
                """,
                (workspace_key,),
            ).fetchall()
            edges = connection.execute(
                """
                SELECT source_path, target_path
                FROM refs
                WHERE workspace_key = ? AND target_path IS NOT NULL
                """,
                (workspace_key,),
            ).fetchall()

        filtered = [
            row
            for row in rows
            if root_prefix is None
            or row["path"] == root_prefix
            or row["path"].startswith(root_prefix + "/")
        ]
        scored: dict[str, dict[str, Any]] = {}
        for row in filtered:
            score, reasons, matching_symbols = self._score(
                path=row["path"],
                symbols=(row["symbols"].split(chr(31)) if row["symbols"] else []),
                tokens=tokens,
                raw_query=text,
            )
            if score <= 0:
                continue
            scored[row["path"]] = {
                "path": row["path"],
                "language": row["language"],
                "score": score,
                "reasons": reasons,
                "matching_symbols": matching_symbols[:8],
            }

        seed_paths = {
            item["path"]
            for item in sorted(
                scored.values(),
                key=lambda item: (-item["score"], item["path"]),
            )[: max(limit, 5)]
        }
        neighbors: dict[str, set[str]] = defaultdict(set)
        for edge in edges:
            source = edge["source_path"]
            target = edge["target_path"]
            neighbors[source].add(target)
            neighbors[target].add(source)
        row_by_path = {row["path"]: row for row in filtered}
        for seed in seed_paths:
            for neighbor in sorted(neighbors.get(seed, ())):
                if neighbor not in row_by_path:
                    continue
                item = scored.setdefault(
                    neighbor,
                    {
                        "path": neighbor,
                        "language": row_by_path[neighbor]["language"],
                        "score": 0,
                        "reasons": [],
                        "matching_symbols": [],
                    },
                )
                item["score"] += 12
                reason = f"dependency of {seed}"
                if reason not in item["reasons"]:
                    item["reasons"].append(reason)

        results = sorted(
            scored.values(),
            key=lambda item: (-item["score"], item["path"]),
        )[:limit]
        return {
            "query": text,
            "tokens": tokens,
            "workspace": str(workspace),
            "project_root": root_prefix or ".",
            "results": results,
            "result_count": len(results),
            "index": self.status(),
            "refresh": refresh_result.get("refresh") if refresh_result else None,
        }

    def _initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    workspace_key TEXT PRIMARY KEY,
                    workspace TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    indexed_at TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    file_count INTEGER NOT NULL,
                    symbol_count INTEGER NOT NULL,
                    reference_count INTEGER NOT NULL,
                    scan_truncated INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT
                );

                CREATE TABLE IF NOT EXISTS files (
                    workspace_key TEXT NOT NULL,
                    path TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    language TEXT NOT NULL,
                    PRIMARY KEY (workspace_key, path)
                );

                CREATE TABLE IF NOT EXISTS symbols (
                    workspace_key TEXT NOT NULL,
                    path TEXT NOT NULL,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    line INTEGER NOT NULL,
                    PRIMARY KEY (workspace_key, path, name, kind, line)
                );

                CREATE TABLE IF NOT EXISTS refs (
                    workspace_key TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    reference TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    target_path TEXT,
                    PRIMARY KEY (
                        workspace_key, source_path, reference, kind
                    )
                );

                CREATE INDEX IF NOT EXISTS idx_symbols_workspace_name
                    ON symbols (workspace_key, name);
                CREATE INDEX IF NOT EXISTS idx_refs_workspace_target
                    ON refs (workspace_key, target_path);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _discover(
        self,
        workspace: Path,
    ) -> tuple[dict[str, tuple[int, int]], bool]:
        result: dict[str, tuple[int, int]] = {}
        truncated = False
        ignore_spec = self._load_ignore_spec(workspace)
        for target in self._walk(workspace, ignore_spec=ignore_spec):
            if len(result) >= self.max_files:
                truncated = True
                break
            try:
                stat = target.stat()
                if stat.st_size > self.max_file_bytes:
                    continue
                relative = target.relative_to(workspace).as_posix()
            except (OSError, ValueError):
                continue
            result[relative] = (stat.st_size, stat.st_mtime_ns)
        return result, truncated

    def _walk(
        self,
        root: Path,
        *,
        ignore_spec: PathSpec | None,
    ) -> Iterator[Path]:
        stack = [root]
        while stack:
            directory = stack.pop()
            try:
                entries = sorted(
                    os.scandir(directory),
                    key=lambda entry: entry.name.casefold(),
                    reverse=True,
                )
            except (OSError, PermissionError):
                continue
            directories: list[Path] = []
            files: list[Path] = []
            for entry in entries:
                if entry.is_symlink() or entry.name in IGNORED_DIRECTORIES:
                    continue
                try:
                    relative = Path(entry.path).relative_to(root).as_posix()
                except ValueError:
                    continue
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if ignore_spec and ignore_spec.match_file(relative + "/"):
                            continue
                        directories.append(Path(entry.path))
                    elif (
                        entry.is_file(follow_symlinks=False)
                        and Path(entry.name).suffix.lower() in INDEXED_SUFFIXES
                    ):
                        if ignore_spec and ignore_spec.match_file(relative):
                            continue
                        files.append(Path(entry.path))
                except OSError:
                    continue
            yield from reversed(files)
            stack.extend(directories)

    @staticmethod
    def _load_ignore_spec(workspace: Path) -> PathSpec | None:
        ignore_file = workspace / ".gitignore"
        if not ignore_file.is_file():
            return None
        try:
            lines = ignore_file.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            return None
        return GitIgnoreSpec.from_lines(lines)

    @staticmethod
    def _language_for(path: Path) -> str:
        return {
            ".py": "python",
            ".pyi": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".mjs": "javascript",
            ".cs": "csharp",
            ".css": "css",
            ".html": "html",
        }.get(path.suffix.lower(), "text")

    def _parse(
        self,
        *,
        content: str,
        language: str,
    ) -> tuple[list[tuple[str, str, int]], list[tuple[str, str]]]:
        if language == "python":
            return self._parse_python(content)
        if language in {"typescript", "javascript"}:
            return self._parse_javascript(content)
        if language == "csharp":
            return self._parse_csharp(content)
        return [], []

    @staticmethod
    def _parse_python(
        content: str,
    ) -> tuple[list[tuple[str, str, int]], list[tuple[str, str]]]:
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return [], []
        symbols: list[tuple[str, str, int]] = []
        references: list[tuple[str, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append((node.name, "function", node.lineno))
            elif isinstance(node, ast.ClassDef):
                symbols.append((node.name, "class", node.lineno))
            elif isinstance(node, ast.Import):
                references.extend((alias.name, "import") for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = "." * node.level + (node.module or "")
                if module:
                    references.append((module, "import"))
        return symbols, references

    @staticmethod
    def _parse_javascript(
        content: str,
    ) -> tuple[list[tuple[str, str, int]], list[tuple[str, str]]]:
        symbols = []
        for match in JS_SYMBOL_PATTERN.finditer(content):
            kind = match.group(1) or "variable"
            name = match.group(2) or match.group(3)
            symbols.append((name, kind, content.count("\n", 0, match.start()) + 1))
        references = []
        for match in JS_IMPORT_PATTERN.finditer(content):
            reference = next(
                (group for group in match.groups() if group is not None),
                None,
            )
            if reference:
                references.append((reference, "import"))
        return symbols, references

    @staticmethod
    def _parse_csharp(
        content: str,
    ) -> tuple[list[tuple[str, str, int]], list[tuple[str, str]]]:
        symbols = [
            (
                match.group(2),
                match.group(1),
                content.count("\n", 0, match.start()) + 1,
            )
            for match in CS_SYMBOL_PATTERN.finditer(content)
        ]
        references = [
            (match.group(1), "using") for match in CS_USING_PATTERN.finditer(content)
        ]
        return symbols, references

    def _replace_file(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_key: str,
        path: str,
        size: int,
        mtime_ns: int,
        sha256: str,
        language: str,
        symbols: Sequence[tuple[str, str, int]],
        references: Sequence[tuple[str, str]],
    ) -> None:
        self._delete_file_rows(connection, workspace_key, path)
        connection.execute(
            """
            INSERT INTO files (
                workspace_key, path, size, mtime_ns, sha256, language
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (workspace_key, path, size, mtime_ns, sha256, language),
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO symbols (
                workspace_key, path, name, kind, line
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [(workspace_key, path, name, kind, line) for name, kind, line in symbols],
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO refs (
                workspace_key, source_path, reference, kind, target_path
            ) VALUES (?, ?, ?, ?, NULL)
            """,
            [(workspace_key, path, reference, kind) for reference, kind in references],
        )

    @staticmethod
    def _delete_file_rows(
        connection: sqlite3.Connection,
        workspace_key: str,
        path: str,
    ) -> None:
        connection.execute(
            "DELETE FROM symbols WHERE workspace_key = ? AND path = ?",
            (workspace_key, path),
        )
        connection.execute(
            "DELETE FROM refs WHERE workspace_key = ? AND source_path = ?",
            (workspace_key, path),
        )
        connection.execute(
            "DELETE FROM files WHERE workspace_key = ? AND path = ?",
            (workspace_key, path),
        )

    @staticmethod
    def _delete_workspace_rows(
        connection: sqlite3.Connection,
        workspace_key: str,
    ) -> None:
        connection.execute(
            "DELETE FROM symbols WHERE workspace_key = ?",
            (workspace_key,),
        )
        connection.execute(
            "DELETE FROM refs WHERE workspace_key = ?",
            (workspace_key,),
        )
        connection.execute(
            "DELETE FROM files WHERE workspace_key = ?",
            (workspace_key,),
        )

    def _resolve_edges(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_key: str,
    ) -> None:
        paths = {
            row["path"]
            for row in connection.execute(
                "SELECT path FROM files WHERE workspace_key = ?",
                (workspace_key,),
            )
        }
        basename_map: dict[str, list[str]] = defaultdict(list)
        for path in paths:
            basename_map[Path(path).stem.casefold()].append(path)
        rows = connection.execute(
            """
            SELECT source_path, reference, kind
            FROM refs
            WHERE workspace_key = ?
            """,
            (workspace_key,),
        ).fetchall()
        for row in rows:
            target = self._resolve_reference(
                source_path=row["source_path"],
                reference=row["reference"],
                paths=paths,
                basename_map=basename_map,
            )
            connection.execute(
                """
                UPDATE refs
                SET target_path = ?
                WHERE workspace_key = ? AND source_path = ?
                  AND reference = ? AND kind = ?
                """,
                (
                    target,
                    workspace_key,
                    row["source_path"],
                    row["reference"],
                    row["kind"],
                ),
            )

    @staticmethod
    def _resolve_reference(
        *,
        source_path: str,
        reference: str,
        paths: set[str],
        basename_map: dict[str, list[str]],
    ) -> str | None:
        source = Path(source_path)
        candidates: list[Path] = []
        if reference.startswith(("./", "../")):
            candidates.append(source.parent / reference)
        elif reference.startswith(("@/", "~/")):
            candidates.append(Path(reference[2:]))
        elif reference.startswith("."):
            level = len(reference) - len(reference.lstrip("."))
            base = source.parent
            for _ in range(max(0, level - 1)):
                base = base.parent
            module = reference[level:].replace(".", "/")
            candidates.append(base / module)
        elif "/" not in reference and "." in reference:
            candidates.append(Path(reference.replace(".", "/")))
        else:
            candidates.append(Path(reference))

        suffixes = ("", ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".cs")
        for base in candidates:
            normalized = Path(os.path.normpath(str(base))).as_posix().lstrip("./")
            for suffix in suffixes:
                candidate = normalized + suffix
                if candidate in paths:
                    return candidate
                suffix_matches = [
                    path
                    for path in basename_map.get(
                        Path(candidate).stem.casefold(),
                        [],
                    )
                    if path.endswith("/" + candidate)
                ]
                if len(suffix_matches) == 1:
                    return suffix_matches[0]
            for index_name in (
                "__init__.py",
                "index.ts",
                "index.tsx",
                "index.js",
                "index.jsx",
            ):
                candidate = f"{normalized.rstrip('/')}/{index_name}"
                if candidate in paths:
                    return candidate
                suffix_matches = [
                    path
                    for path in basename_map.get(Path(index_name).stem, [])
                    if path.endswith("/" + candidate)
                ]
                if len(suffix_matches) == 1:
                    return suffix_matches[0]

        if not reference.startswith((".", "/", "@", "~")):
            matches = basename_map.get(reference.rsplit(".", 1)[-1].casefold(), [])
            if len(matches) == 1:
                return matches[0]
        return None

    @staticmethod
    def _score(
        *,
        path: str,
        symbols: Sequence[str],
        tokens: Sequence[str],
        raw_query: str,
    ) -> tuple[int, list[str], list[str]]:
        path_lower = path.casefold()
        basename = Path(path).name.casefold()
        stem = Path(path).stem.casefold()
        symbol_map = {symbol.casefold(): symbol for symbol in symbols}
        score = 0
        reasons: list[str] = []
        matching_symbols: list[str] = []

        normalized_query = raw_query.replace("\\", "/").casefold()
        if path_lower in normalized_query:
            score += 100
            reasons.append("exact path in task")
        for token in tokens:
            if token == stem:
                score += 32
                reasons.append(f"filename matches '{token}'")
            elif token in basename:
                score += 18
                reasons.append(f"filename contains '{token}'")
            elif token in path_lower:
                score += 8
                reasons.append(f"path contains '{token}'")
            if token in symbol_map:
                score += 28
                matching_symbols.append(symbol_map[token])
            else:
                matched = [
                    original for name, original in symbol_map.items() if token in name
                ]
                if matched:
                    score += 12
                    matching_symbols.extend(matched[:3])
        if matching_symbols:
            reasons.append("symbols: " + ", ".join(dict.fromkeys(matching_symbols[:5])))
        if basename in MANIFEST_NAMES:
            score += 2
        return (
            score,
            list(dict.fromkeys(reasons)),
            list(dict.fromkeys(matching_symbols)),
        )

    @staticmethod
    def _query_tokens(text: str) -> list[str]:
        tokens: list[str] = []
        for match in TOKEN_PATTERN.findall(text):
            parts = CAMEL_BOUNDARY_PATTERN.sub(" ", match).replace("_", " ").split()
            for part in parts:
                token = part.casefold()
                if len(token) >= 2 and token not in STOP_WORDS and token not in tokens:
                    tokens.append(token)
        return tokens[:40]

    @staticmethod
    def _normalize_project_root(project_root: str | None) -> str | None:
        if not project_root or project_root == ".":
            return None
        clean = project_root.strip().replace("\\", "/").strip("/")
        if not clean or ".." in Path(clean).parts:
            raise ValueError("Project root must be workspace-relative")
        return clean

    def _record_error(
        self,
        *,
        workspace_key: str,
        workspace: Path,
        error: str,
        duration_ms: int,
    ) -> None:
        try:
            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO workspaces (
                        workspace_key, workspace, schema_version, indexed_at,
                        duration_ms, file_count, symbol_count, reference_count,
                        scan_truncated, last_error
                    ) VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0, ?)
                    ON CONFLICT(workspace_key) DO UPDATE SET
                        indexed_at = excluded.indexed_at,
                        duration_ms = excluded.duration_ms,
                        last_error = excluded.last_error
                    """,
                    (
                        workspace_key,
                        str(workspace),
                        self.SCHEMA_VERSION,
                        self._utc_now(),
                        duration_ms,
                        error[:2000],
                    ),
                )
        except sqlite3.Error:
            pass

    @staticmethod
    def _workspace_key(workspace: Path) -> str:
        normalized = os.path.normcase(str(workspace.resolve()))
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def debug_snapshot(self) -> str:
        """Return metadata for diagnostics without exposing source contents."""
        return json.dumps(self.status(), sort_keys=True)
