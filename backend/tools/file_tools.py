from typing import Dict, List

from dependencies import workspace_service


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


def read_file(file_path: str) -> Dict[str, str]:
    workspace_root = workspace_service.get_workspace()
    path = workspace_service.resolve_workspace_path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not path.is_file():
        raise IsADirectoryError(f"Not a file: {file_path}")

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(
            f"File is not a readable UTF-8 text file: {file_path}"
        ) from error

    return {
        "path": str(path.relative_to(workspace_root)),
        "content": content,
    }


def write_file(
    file_path: str,
    content: str,
    overwrite: bool = False,
) -> Dict[str, str]:
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

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        content,
        encoding="utf-8",
    )

    return {
        "path": str(path.relative_to(workspace_root)),
        "status": "overwritten" if overwrite else "created",
    }