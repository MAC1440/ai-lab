from copy import deepcopy
from typing import Any, Dict, Iterable, List


ToolSchema = Dict[str, Any]


TOOL_SCHEMAS: Dict[str, ToolSchema] = {
    "list_files": {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "List the immediate files and folders inside a directory "
                "in the currently selected workspace. Use this to discover "
                "the project structure before attempting to read files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {
                        "type": "string",
                        "description": (
                            "A path relative to the selected workspace. "
                            "Use '.' for the workspace root. Examples: "
                            "'backend', 'frontend/app', or '.'."
                        ),
                    }
                },
                "required": ["folder"],
                "additionalProperties": False,
            },
        },
    },
    "read_file": {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the complete UTF-8 text content of one file inside "
                "the selected workspace. Use only paths discovered from "
                "list_files or explicitly provided by the user."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": (
                            "The file path relative to the selected workspace. "
                            "Example: 'backend/main.py'."
                        ),
                    }
                },
                "required": ["file_path"],
                "additionalProperties": False,
            },
        },
    },
}


def get_tool_schemas(
    allowed_tool_names: Iterable[str],
) -> List[ToolSchema]:
    """
    Return only schemas that are both:
    1. allowed for the selected agent; and
    2. currently exposed to the LLM.

    write_file is deliberately not included in TOOL_SCHEMAS yet, even though
    the coding profile may use it through the manually tested HTTP route.
    """

    schemas: List[ToolSchema] = []

    for tool_name in allowed_tool_names:
        schema = TOOL_SCHEMAS.get(tool_name)

        if schema is not None:
            schemas.append(deepcopy(schema))

    return schemas