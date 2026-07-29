from __future__ import annotations

import ast
import sys
from pathlib import Path


def replacement(old: str, new: str) -> tuple[str, str]:
    return old, new


PATCHES: dict[str, list[tuple[str, str]]] = {
    "backend/services/provider_settings_service.py": [
        replacement(
            '''from pydantic import BaseModel, Field, field_validator


ProviderKind = Literal["ollama", "openai_compatible"]
''',
            '''from pydantic import BaseModel, Field, field_validator

from services.ollama_runtime import routes_to_ollama_cloud


ProviderKind = Literal["ollama", "openai_compatible"]
''',
        ),
        replacement(
            '''            if provider["kind"] == "ollama":
                response = httpx.get(
                    f"{provider['base_url']}/api/tags", timeout=15.0
                )
                response.raise_for_status()
                raw_models = response.json().get("models", [])
                models = [
                    {
                        "name": item.get("name") or item.get("model"),
                        "size": item.get("size"),
                        "modified_at": item.get("modified_at"),
                        "warnings": self._model_warnings(
                            item.get("name") or item.get("model") or "",
                            item.get("size"),
                        ),
                    }
                    for item in raw_models
                    if item.get("name") or item.get("model")
                ]
''',
            '''            if provider["kind"] == "ollama":
                response = httpx.get(
                    f"{provider['base_url']}/api/tags",
                    headers=headers,
                    timeout=15.0,
                )
                response.raise_for_status()
                raw_models = response.json().get("models", [])
                models = []
                for item in raw_models:
                    model_name = item.get("name") or item.get("model")
                    if not model_name:
                        continue
                    is_cloud = routes_to_ollama_cloud(
                        provider,
                        model_name,
                    )
                    warnings = (
                        [
                            "This model runs remotely. Prompts, retrieved "
                            "context, and tool-call arguments are sent to "
                            "Ollama Cloud."
                        ]
                        if is_cloud
                        else self._model_warnings(
                            model_name,
                            item.get("size"),
                        )
                    )
                    models.append(
                        {
                            "name": model_name,
                            "size": None if is_cloud else item.get("size"),
                            "modified_at": item.get("modified_at"),
                            "warnings": warnings,
                        }
                    )
''',
        ),
        replacement(
            '''        if kind == "ollama" and clean.endswith("/v1"):
            clean = clean[:-3].rstrip("/")
        if kind == "openai_compatible" and not clean.endswith("/v1"):
''',
            '''        if kind == "ollama":
            for suffix in ("/v1", "/api"):
                if clean.endswith(suffix):
                    clean = clean[: -len(suffix)].rstrip("/")
        if kind == "openai_compatible" and not clean.endswith("/v1"):
''',
        ),
    ],
    "backend/services/model_capability_service.py": [
        replacement(
            '''from pydantic import BaseModel, Field, field_validator


StructuredOutputMode = Literal["native", "tool", "unsupported"]
''',
            '''from pydantic import BaseModel, Field, field_validator

from services.ollama_runtime import is_ollama_cloud_runtime


StructuredOutputMode = Literal["native", "tool", "unsupported"]
''',
        ),
        replacement(
            '''            structured_mode = (
                "native" if provider_kind == "ollama" else "tool"
            )
''',
            '''            structured_mode = (
                "native"
                if provider_kind == "ollama"
                and not is_ollama_cloud_runtime(runtime)
                else "tool"
            )
''',
        ),
        replacement(
            '''        else:
            profile = deepcopy(saved)
            profile["profile_source"] = "saved"

        effective_context = min(
''',
            '''        else:
            profile = deepcopy(saved)
            profile["profile_source"] = "saved"

        if (
            is_ollama_cloud_runtime(runtime)
            and profile.get("structured_output_mode") == "native"
        ):
            profile["structured_output_mode"] = "tool"
            profile["structured_output_fallback"] = "ollama_cloud"

        effective_context = min(
''',
        ),
    ],
    "backend/services/pydantic_agent.py": [
        replacement(
            '''from services.agent_service import AgentService
from services.pydantic_model import build_pydantic_model
''',
            '''from services.agent_service import AgentService
from services.ollama_runtime import ollama_model_settings_extra_body
from services.pydantic_model import build_pydantic_model
''',
        ),
        replacement(
            '''    if runtime.get("provider", {}).get("kind") == "ollama":
        model_settings["extra_body"] = {
            "options":{
                "num_ctx": generation["context_window"]
            }
        }
''',
            '''    extra_body = ollama_model_settings_extra_body(
        runtime,
        generation["context_window"],
    )
    if extra_body is not None:
        model_settings["extra_body"] = extra_body
''',
        ),
    ],
    "backend/services/task_model_client.py": [
        replacement(
            '''from services.agent_service import AgentService
from services.task_model_output_adapter import (
''',
            '''from services.agent_service import AgentService
from services.ollama_runtime import (
    is_ollama_cloud_runtime,
    ollama_model_settings_extra_body,
)
from services.task_model_output_adapter import (
''',
        ),
        replacement(
            '''            "structured_output_mode": (
                "native"
                if runtime.get("provider", {}).get("kind") == "ollama"
                else "tool"
            ),
''',
            '''            "structured_output_mode": (
                "native"
                if runtime.get("provider", {}).get("kind") == "ollama"
                and not is_ollama_cloud_runtime(runtime)
                else "tool"
            ),
''',
        ),
        replacement(
            '''        run_arguments = {
            "usage_limits": UsageLimits(request_limit=self.request_limit),
            "model_settings": ModelSettings(
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body={"options": {"num_ctx": context_window}}
                if runtime.get("provider", {}).get("kind") == "ollama"
                else None,
            ),
        }
''',
            '''        extra_body = ollama_model_settings_extra_body(
            runtime,
            context_window,
        )
        run_arguments = {
            "usage_limits": UsageLimits(request_limit=self.request_limit),
            "model_settings": ModelSettings(
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body=extra_body,
            ),
        }
''',
        ),
    ],
}


REQUIRED_PAYLOADS = (
    "backend/services/ollama_runtime.py",
    "backend/services/pydantic_model.py",
    "backend/tests/test_ollama_cloud_support.py",
)


def apply(root: Path) -> list[str]:
    missing = [
        relative
        for relative in (*PATCHES.keys(), *REQUIRED_PAYLOADS)
        if not (root / relative).is_file()
    ]
    if missing:
        joined = "\n  - ".join(missing)
        raise RuntimeError(
            "The code drop is incomplete or was not extracted at the project "
            f"root. Missing:\n  - {joined}"
        )

    staged: dict[Path, str] = {}
    changed: list[str] = []

    for relative, replacements in PATCHES.items():
        path = root / relative
        text = path.read_text(encoding="utf-8")
        updated = text

        for old, new in replacements:
            if new in updated:
                continue

            occurrences = updated.count(old)
            if occurrences != 1:
                raise RuntimeError(
                    f"Refusing to patch {relative}: expected one matching "
                    f"source block, found {occurrences}. No files were changed."
                )
            updated = updated.replace(old, new, 1)

        ast.parse(updated, filename=str(path))
        staged[path] = updated
        if updated != text:
            changed.append(relative)

    for relative in REQUIRED_PAYLOADS:
        path = root / relative
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    for path, text in staged.items():
        temporary = path.with_suffix(path.suffix + ".ollama-cloud.tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)

    return changed


def main() -> int:
    project_root = (
        Path(sys.argv[1]).resolve()
        if len(sys.argv) > 1
        else Path.cwd().resolve()
    )

    try:
        changed = apply(project_root)
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if changed:
        print("Ollama Cloud code drop applied:")
        for relative in changed:
            print(f"  - updated {relative}")
    else:
        print("Ollama Cloud code drop was already applied.")

    print("Payload files present:")
    for relative in REQUIRED_PAYLOADS:
        print(f"  - {relative}")
    print()
    print("Run from the backend folder:")
    print(
        "python -m pytest -q "
        "tests/test_ollama_cloud_support.py "
        "tests/test_provider_settings_service.py "
        "tests/test_task_model_client.py"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
