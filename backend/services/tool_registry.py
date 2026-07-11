from typing import Any, Dict, List


ToolSchema = Dict[str, Any]


READ_ONLY_TOOL_SCHEMAS: List[ToolSchema] = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "List the files and folders inside a directory in the "
                "currently selected workspace. Use relative workspace paths."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {
                        "type": "string",
                        "description": (
                            "Relative folder path inside the selected workspace. "
                            "Use '.' for the workspace root."
                        ),
                    }
                },
                "required": ["folder"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the UTF-8 text contents of a file inside the currently "
                "selected workspace. Use a relative workspace path."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": (
                            "Relative path to the file inside the selected workspace."
                        ),
                    }
                },
                "required": ["file_path"],
            },
        },
    },
]