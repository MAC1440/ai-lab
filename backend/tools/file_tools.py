from typing import Dict, List

from dependencies import workspace_service


def list_files(folder: str = ".") -> List[Dict[str, str]]:
    workspace_root = workspace_service.get_workspace()
    path = workspace_service.resolve_workspace_path(folder)

    if not path.exists():
        raise FileNotFoundError(f"Folder not found: {folder}")

    if not path.is_dir():
        raise NotADirectoryError(f"Not a folder: {folder}")

    items = []

    for item in path.iterdir():
        items.append(
            {
                "name": item.name,
                "path": str(item.relative_to(workspace_root)),
                "type": "folder" if item.is_dir() else "file",
            }
        )

    return items


def read_file(file_path: str) -> Dict[str, str]:
    workspace_root = workspace_service.get_workspace()
    path = workspace_service.resolve_workspace_path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not path.is_file():
        raise IsADirectoryError(f"Not a file: {file_path}")

    return {
        "path": str(path.relative_to(workspace_root)),
        "content": path.read_text(encoding="utf-8"),
    }