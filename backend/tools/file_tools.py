from pathlib import Path
from typing import List, Dict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def safe_path(relative_path: str) -> Path:
    """
    Convert a user-provided relative path into a safe absolute path.
    Prevents access outside backend folder.
    """
    target_path = (PROJECT_ROOT / relative_path).resolve()

    if not str(target_path).startswith(str(PROJECT_ROOT)):
        raise ValueError("Access outside project root is not allowed")

    return target_path


def list_files(folder: str = ".") -> List[Dict[str, str]]:
    path = safe_path(folder)

    if not path.exists():
        raise FileNotFoundError(f"Folder not found: {folder}")

    if not path.is_dir():
        raise NotADirectoryError(f"Not a folder: {folder}")

    files = []

    for item in path.iterdir():
        files.append({
            "name": item.name,
            "path": str(item.relative_to(PROJECT_ROOT)),
            "type": "folder" if item.is_dir() else "file",
        })

    return files


def read_file(file_path: str) -> Dict[str, str]:
    path = safe_path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not path.is_file():
        raise IsADirectoryError(f"Not a file: {file_path}")

    return {
        "path": str(path.relative_to(PROJECT_ROOT)),
        "content": path.read_text(encoding="utf-8"),
    }