from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional


class WorkspaceService:
    def __init__(self):
        self._active_workspace: Optional[Path] = None
        self._lock = Lock()

    def list_drives(self) -> List[str]:
        """
        Return available Windows drives such as C:\\ and D:\\.
        """
        drives = []

        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = Path(f"{letter}:/")

            if drive.exists():
                drives.append(str(drive))

        return drives

    def list_directory(self, absolute_path: str) -> List[Dict[str, str]]:
        """
        Used by the human-facing folder browser before a workspace is selected.
        """
        path = Path(absolute_path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Path not found: {absolute_path}")

        if not path.is_dir():
            raise NotADirectoryError(f"Not a folder: {absolute_path}")

        items = []

        for item in path.iterdir():
            try:
                items.append(
                    {
                        "name": item.name,
                        "path": str(item),
                        "type": "folder" if item.is_dir() else "file",
                    }
                )
            except PermissionError:
                # Some Windows folders cannot be inspected.
                continue

        return sorted(
            items,
            key=lambda item: (
                item["type"] != "folder",
                item["name"].lower(),
            ),
        )

    def set_workspace(self, absolute_path: str) -> Dict[str, str]:
        path = Path(absolute_path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"Workspace not found: {absolute_path}")

        if not path.is_dir():
            raise NotADirectoryError("Workspace must be a folder")

        with self._lock:
            self._active_workspace = path

        return {
            "workspace": str(path),
        }

    def get_workspace(self) -> Path:
        if self._active_workspace is None:
            raise RuntimeError("No workspace has been selected")

        return self._active_workspace

    def get_workspace_info(self) -> Dict[str, Optional[str]]:
        return {
            "workspace": (
                str(self._active_workspace)
                if self._active_workspace
                else None
            )
        }

    def resolve_workspace_path(self, relative_path: str = ".") -> Path:
        root = self.get_workspace()
        target = (root / relative_path).resolve()

        try:
            target.relative_to(root)
        except ValueError as error:
            raise PermissionError(
                "Access outside the active workspace is not allowed"
            ) from error

        return target