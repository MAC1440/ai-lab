from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, List

from dependencies import change_service, workspace_service

IGNORED_DIRECTORIES = {
    ".git",
    ".next",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}


def list_files(folder: str = ".") -> List[Dict[str, str]]:
    workspace_root = workspace_service.get_workspace()
    folder_path = workspace_service.resolve_workspace_path(folder)

    if not folder_path.exists():
        raise FileNotFoundError(f"Folder not found: {folder}")
    if not folder_path.is_dir():
        raise NotADirectoryError(f"Not a folder: {folder}")

    items: List[Dict[str, str]] = []
    for item in folder_path.iterdir():
        items.append(
            {
                "name": item.name,
                "path": str(item.relative_to(workspace_root)),
                "type": "folder" if item.is_dir() else "file",
            }
        )

    items.sort(
        key=lambda item: (
            item["type"] != "folder",
            item["name"].lower(),
        )
    )
    return items


def search_files(
    query: str,
    folder: str = ".",
    max_results: int = 50,
) -> List[Dict[str, str]]:
    clean_query = _require_non_empty_string(query, "query").lower()
    clean_folder = _require_non_empty_string(folder, "folder")
    limit = _validate_limit(max_results)

    workspace_root = workspace_service.get_workspace()
    folder_path = workspace_service.resolve_workspace_path(clean_folder)
    if not folder_path.exists():
        raise FileNotFoundError(f"Folder not found: {clean_folder}")
    if not folder_path.is_dir():
        raise NotADirectoryError(f"Not a folder: {clean_folder}")

    results: List[Dict[str, str]] = []
    for path in folder_path.rglob("*"):
        relative = path.relative_to(workspace_root)
        if _is_ignored(relative):
            continue
        relative_text = str(relative)
        if clean_query not in relative_text.lower():
            continue
        results.append(
            {
                "name": path.name,
                "path": relative_text,
                "type": "folder" if path.is_dir() else "file",
            }
        )
        if len(results) >= limit:
            break

    results.sort(key=lambda item: (item["type"] != "folder", item["path"].lower()))
    return results


def read_file(file_path: str) -> Dict[str, str]:
    workspace_root = workspace_service.get_workspace()
    path = workspace_service.resolve_workspace_path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not path.is_file():
        raise IsADirectoryError(f"Not a file: {file_path}")

    try:
        content = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(
            f"File is not a readable UTF-8 text file: {file_path}"
        ) from error

    return {
        "path": str(path.relative_to(workspace_root)),
        "content": content,
    }


def read_file_range(
    file_path: str,
    start_line: int = 1,
    end_line: int = 200,
) -> Dict[str, Any]:
    clean_path = _require_non_empty_string(file_path, "file_path")
    if not isinstance(start_line, int) or isinstance(start_line, bool):
        raise ValueError("start_line must be an integer")
    if not isinstance(end_line, int) or isinstance(end_line, bool):
        raise ValueError("end_line must be an integer")
    if start_line < 1:
        raise ValueError("start_line must be at least 1")
    if end_line < start_line:
        raise ValueError("end_line must be greater than or equal to start_line")
    if end_line - start_line + 1 > 400:
        raise ValueError("A single read_file_range call may return at most 400 lines")

    workspace_root = workspace_service.get_workspace()
    path = workspace_service.resolve_workspace_path(clean_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {clean_path}")
    if not path.is_file():
        raise IsADirectoryError(f"Not a file: {clean_path}")

    try:
        lines = path.read_bytes().decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError as error:
        raise ValueError(
            f"File is not a readable UTF-8 text file: {clean_path}"
        ) from error

    total_lines = len(lines)
    selected = lines[start_line - 1 : end_line]
    actual_end = min(end_line, total_lines)
    return {
        "path": str(path.relative_to(workspace_root)),
        "start_line": start_line,
        "end_line": actual_end,
        "total_lines": total_lines,
        "content": "".join(selected),
    }


def search_text(
    query: str,
    folder: str = ".",
    file_glob: str = "*",
    max_results: int = 50,
) -> List[Dict[str, Any]]:
    clean_query = _require_non_empty_string(query, "query")
    clean_folder = _require_non_empty_string(folder, "folder")
    clean_glob = _require_non_empty_string(file_glob, "file_glob")
    limit = _validate_limit(max_results)

    workspace_root = workspace_service.get_workspace()
    folder_path = workspace_service.resolve_workspace_path(clean_folder)
    if not folder_path.exists():
        raise FileNotFoundError(f"Folder not found: {clean_folder}")
    if not folder_path.is_dir():
        raise NotADirectoryError(f"Not a folder: {clean_folder}")

    needle = clean_query.lower()
    results: List[Dict[str, Any]] = []
    for path in folder_path.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(workspace_root)
        if _is_ignored(relative) or not fnmatch(path.name, clean_glob):
            continue
        try:
            if path.stat().st_size > 1_000_000:
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        for line_number, line in enumerate(lines, start=1):
            if needle not in line.lower():
                continue
            results.append(
                {
                    "path": str(relative),
                    "line_number": line_number,
                    "line": line[:500],
                }
            )
            if len(results) >= limit:
                return results

    return results


def propose_file_change(
    file_path: str,
    new_text: str,
    old_text: str = "",
    summary: str = "",
    change_set_id: str | None = None,
    repair_task_id: str | None = None,
) -> Dict[str, Any]:
    """Create a reviewable proposal without writing the file.

    Two proposal modes are supported:

    1. Exact replacement mode: provide a unique ``old_text`` snippet and the
       replacement ``new_text``. This is efficient for small edits.
    2. Full-file mode: omit ``old_text`` and provide the complete desired file
       content in ``new_text``. This is more tolerant of small local models
       that occasionally omit optional tool arguments.

    Both modes only create a diff. The file is written later only if a human
    approves the proposal.
    """

    clean_path = _require_non_empty_string(file_path, "file_path")
    if not isinstance(old_text, str):
        raise ValueError("old_text must be a string")
    if not isinstance(new_text, str):
        raise ValueError("new_text must be a string")

    path = workspace_service.resolve_workspace_path(clean_path)
    if path.exists() and path.is_dir():
        raise IsADirectoryError(f"Not a file: {clean_path}")

    if not path.exists():
        if old_text:
            raise ValueError(
                "old_text must be empty when proposing a new file"
            )
        proposed_content = new_text
    else:
        try:
            current_content = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(
                f"File is not a readable UTF-8 text file: {clean_path}"
            ) from error

        if old_text:
            proposed_content = _replace_unique_text(
                current_content=current_content,
                old_text=old_text,
                new_text=new_text,
            )
        else:
            proposed_content = new_text

    proposal = change_service.propose(
        file_path=clean_path,
        content=proposed_content,
        summary=summary,
        change_set_id=change_set_id,
        repair_task_id=repair_task_id,
    )
    return {"proposal": proposal}


def _replace_unique_text(
    *,
    current_content: str,
    old_text: str,
    new_text: str,
) -> str:
    """Replace one exact snippet while tolerating Windows line endings.

    Tool arguments are JSON strings, so small models commonly send ``\n``
    even when the selected Windows file contains ``\r\n``. The match remains
    strict apart from newline representation: the adapted snippet must still
    occur exactly once. Replacement text adopts the file's dominant newline
    style so an accepted proposal does not create mixed line endings.
    """

    newline = _dominant_newline(current_content)
    replacement_text = (
        _convert_newlines(new_text, newline)
        if newline is not None
        else new_text
    )

    occurrence_count = current_content.count(old_text)
    matched_old_text = old_text

    if occurrence_count == 0 and newline is not None:
        adapted_old_text = _convert_newlines(old_text, newline)
        if adapted_old_text != old_text:
            matched_old_text = adapted_old_text
            occurrence_count = current_content.count(matched_old_text)

    if occurrence_count != 1:
        raise ValueError(
            "old_text must occur exactly once in the current file; "
            f"found {occurrence_count} occurrences"
        )

    return current_content.replace(
        matched_old_text,
        replacement_text,
        1,
    )


def _dominant_newline(content: str) -> str | None:
    crlf_count = content.count("\r\n")
    lf_count = content.count("\n") - crlf_count
    cr_count = content.count("\r") - crlf_count

    counts = (
        (crlf_count, "\r\n"),
        (lf_count, "\n"),
        (cr_count, "\r"),
    )
    count, newline = max(counts, key=lambda item: item[0])
    return newline if count > 0 else None


def _convert_newlines(text: str, newline: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\n", newline)


def write_file(
    file_path: str,
    content: str,
    overwrite: bool = False,
) -> Dict[str, str]:
    """Manual-route helper retained for compatibility.

    This function is deliberately not exposed in the model tool registry.
    Agent-authored changes must go through propose_file_change and approval.
    """

    workspace_root = workspace_service.get_workspace()
    path = workspace_service.resolve_workspace_path(file_path)

    if path.exists() and path.is_dir():
        raise IsADirectoryError(
            f"Cannot write content to a folder: {file_path}"
        )
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"File already exists: {file_path}. "
            "Set overwrite=true to replace it."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {
        "path": str(path.relative_to(workspace_root)),
        "status": "overwritten" if overwrite else "created",
    }


def _is_ignored(relative_path: Path) -> bool:
    return any(part in IGNORED_DIRECTORIES for part in relative_path.parts)


def _require_non_empty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _validate_limit(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("max_results must be an integer")
    if value < 1 or value > 200:
        raise ValueError("max_results must be between 1 and 200")
    return value
