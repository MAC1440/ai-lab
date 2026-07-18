from copy import deepcopy
from typing import Any, Dict, Iterable, List

ToolSchema = Dict[str, Any]

TOOL_SCHEMAS: Dict[str, ToolSchema] = {
    "list_files": {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "List immediate files and folders inside a directory in the "
                "selected workspace."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {
                        "type": "string",
                        "description": "Workspace-relative folder, or '.' for root.",
                    }
                },
                "required": ["folder"],
                "additionalProperties": False,
            },
        },
    },
    "search_files": {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": (
                "Recursively find files or folders whose workspace-relative "
                "path contains a name fragment."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "folder": {"type": "string", "default": "."},
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 200,
                        "default": 50,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    "read_file": {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the complete UTF-8 content of one workspace file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Workspace-relative file path.",
                    }
                },
                "required": ["file_path"],
                "additionalProperties": False,
            },
        },
    },
    "read_file_range": {
        "type": "function",
        "function": {
            "name": "read_file_range",
            "description": (
                "Read a bounded inclusive line range from a UTF-8 workspace file. "
                "Prefer this over read_file for large files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "start_line": {
                        "type": "integer",
                        "minimum": 1,
                        "default": 1,
                    },
                    "end_line": {
                        "type": "integer",
                        "minimum": 1,
                        "default": 200,
                    },
                },
                "required": ["file_path"],
                "additionalProperties": False,
            },
        },
    },
    "search_text": {
        "type": "function",
        "function": {
            "name": "search_text",
            "description": (
                "Recursively search UTF-8 project files for text and return "
                "matching paths, line numbers, and line snippets."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "folder": {"type": "string", "default": "."},
                    "file_glob": {
                        "type": "string",
                        "description": "Filename glob such as '*.py' or '*.tsx'.",
                        "default": "*",
                    },
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 200,
                        "default": 50,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    "propose_file_change": {
        "type": "function",
        "function": {
            "name": "propose_file_change",
            "description": (
                "Create a reviewable file-change proposal and unified diff. "
                "This never writes the file. Prefer an exact unique old_text "
                "for a small replacement. If old_text is omitted, new_text is "
                "treated as the complete proposed file content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Workspace-relative target file path.",
                    },
                    "old_text": {
                        "type": "string",
                        "description": (
                            "Optional exact unique text currently in the file. "
                            "Omit it when new_text contains the complete file."
                        ),
                        "default": "",
                    },
                    "new_text": {
                        "type": "string",
                        "description": (
                            "Replacement text when old_text is supplied, or the "
                            "complete proposed file when old_text is omitted."
                        ),
                    },
                    "summary": {
                        "type": "string",
                        "description": "Brief reason for the proposed change.",
                        "default": "",
                    },
                },
                "required": ["file_path", "new_text"],
                "additionalProperties": False,
            },
        },
    },
    "propose_path_operation": {
        "type": "function",
        "function": {
            "name": "propose_path_operation",
            "description": (
                "Create a reviewable proposal to delete a file, move or rename "
                "a file, or create a directory. This never changes the workspace "
                "until a human approves it. Directory deletion is unsupported."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["delete", "move", "mkdir"],
                    },
                    "file_path": {"type": "string"},
                    "destination_path": {
                        "type": "string",
                        "description": "Required only for move operations.",
                        "default": "",
                    },
                    "summary": {"type": "string", "default": ""},
                },
                "required": ["operation", "file_path"],
                "additionalProperties": False,
            },
        },
    },
}


def GetToolSchemas(
    allowed_tool_names: Iterable[str],
) -> List[ToolSchema]:
    """Return only schemas explicitly allowed for the selected agent."""

    schemas: List[ToolSchema] = []
    for tool_name in allowed_tool_names:
        schema = TOOL_SCHEMAS.get(tool_name)
        if schema is not None:
            schemas.append(deepcopy(schema))
    return schemas
