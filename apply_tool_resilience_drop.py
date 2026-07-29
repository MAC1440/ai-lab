from __future__ import annotations

import ast
import sys
from pathlib import Path


TARGET_COMMIT = "30dec1a86e29a8d4282ba519abb218759f33f235"
ADDED_FILES = ("backend/tests/test_tool_call_resilience.py",)

PATCHES = {'backend/tests/test_provider_settings_service.py': [('    def '
                                                      'test_agent_overrides_are_independent(self):\n'
                                                      '        self.service.save_agent(\n'
                                                      '            "coding",\n'
                                                      '            AgentModelInput(\n'
                                                      '                provider_id="ollama",\n'
                                                      '                model="qwen3:4b",\n'
                                                      '                '
                                                      'generation=GenerationSettings(temperature=0.2),\n'
                                                      '            ),\n'
                                                      '        )\n'
                                                      '        coding = '
                                                      'self.service.resolve_agent("coding")\n'
                                                      '        unity = '
                                                      'self.service.resolve_agent("unity")\n'
                                                      '        self.assertEqual(coding["model"], '
                                                      '"qwen3:4b")\n'
                                                      '        self.assertEqual(unity["model"], '
                                                      '"granite4.1:3b")\n',
                                                      '    def '
                                                      'test_agent_overrides_are_independent(self):\n'
                                                      '        self.service.save_agent(\n'
                                                      '            "coding",\n'
                                                      '            AgentModelInput(\n'
                                                      '                provider_id="ollama",\n'
                                                      '                model="qwen3:4b",\n'
                                                      '                '
                                                      'generation=GenerationSettings(temperature=0.2),\n'
                                                      '            ),\n'
                                                      '        )\n'
                                                      '        coding = '
                                                      'self.service.resolve_agent("coding")\n'
                                                      '        unity = '
                                                      'self.service.resolve_agent("unity")\n'
                                                      '\n'
                                                      '        self.assertEqual(coding["model"], '
                                                      '"qwen3:4b")\n'
                                                      '        '
                                                      'self.assertEqual(coding["assignment_source"], '
                                                      '"agent")\n'
                                                      '        self.assertEqual(unity["model"], '
                                                      '"")\n'
                                                      '        self.assertEqual(\n'
                                                      '            unity["assignment_source"],\n'
                                                      '            "unconfigured",\n'
                                                      '        )\n')],
 'backend/services/agent_service.py': [('CHANGE_SAFETY_PROMPT = (\n'
                                        '    "Every workspace mutation must use a proposal tool '
                                        'and requires human "\n'
                                        '    "approval. Prefer propose_file_change_set for a '
                                        'coherent multi-file "\n'
                                        '    "create/update task, use propose_file_change for one '
                                        'file, and "\n'
                                        '    "propose_path_operation for delete, move/rename, or '
                                        'mkdir. Read every "\n'
                                        '    "existing file before changing, deleting, or moving '
                                        'it. A new file or "\n'
                                        '    "directory does not require a fake read. Never delete '
                                        'a directory. Never "\n'
                                        '    "claim a proposal was applied or a problem was fixed '
                                        'until approval and "\n'
                                        '    "verification have actually succeeded."\n'
                                        ')\n',
                                        'CHANGE_SAFETY_PROMPT = (\n'
                                        '    "Every workspace mutation must use a proposal tool '
                                        'and requires human "\n'
                                        '    "approval. Prefer propose_file_change_set for a '
                                        'coherent multi-file "\n'
                                        '    "create/update task, use propose_file_change for one '
                                        'file, and "\n'
                                        '    "propose_path_operation for delete, move/rename, or '
                                        'mkdir. Read every "\n'
                                        '    "existing file before changing, deleting, or moving '
                                        'it. Use read_file "\n'
                                        '    "with only file_path for a full read, or include '
                                        'start_line and end_line "\n'
                                        '    "for a bounded read; read_file_range is equivalent. '
                                        'After a tool "\n'
                                        '    "validation error, correct the arguments instead of '
                                        'repeating the same "\n'
                                        '    "call. A new file or directory does not require a '
                                        'fake read. Never delete "\n'
                                        '    "a directory. Never claim a proposal was applied or a '
                                        'problem was fixed "\n'
                                        '    "until approval and verification have actually '
                                        'succeeded."\n'
                                        ')\n')],
 'backend/services/pydantic_agent.py': [('def read_file(\n'
                                         '    ctx: RunContext[AgentRunDeps],\n'
                                         '    file_path: str,\n'
                                         ') -> Any:\n'
                                         '    """Read a UTF-8 workspace file using its exact '
                                         'relative path."""\n'
                                         '    try:\n'
                                         '        result = _read_file(file_path)\n'
                                         '        deps = _run_deps(ctx)\n'
                                         '        if deps is not None and isinstance(result, '
                                         'dict):\n'
                                         '            result_path = result.get("path")\n'
                                         '            if isinstance(result_path, str):\n'
                                         '                '
                                         'deps.inspected_paths.add(_normalized_path(result_path))\n'
                                         '        return result\n'
                                         '    except EXPECTED_TOOL_ERRORS as error:\n'
                                         '        return _tool_error(error)\n',
                                         'def read_file(\n'
                                         '    ctx: RunContext[AgentRunDeps],\n'
                                         '    file_path: str,\n'
                                         '    start_line: int | None = None,\n'
                                         '    end_line: int | None = None,\n'
                                         ') -> Any:\n'
                                         '    """Read a UTF-8 file, optionally limiting the '
                                         'inclusive line range."""\n'
                                         '    try:\n'
                                         '        if start_line is None and end_line is None:\n'
                                         '            result = _read_file(file_path)\n'
                                         '        else:\n'
                                         '            resolved_start = 1 if start_line is None '
                                         'else start_line\n'
                                         '            resolved_end = (\n'
                                         '                resolved_start + 199\n'
                                         '                if end_line is None\n'
                                         '                else end_line\n'
                                         '            )\n'
                                         '            result = _read_file_range(\n'
                                         '                file_path=file_path,\n'
                                         '                start_line=resolved_start,\n'
                                         '                end_line=resolved_end,\n'
                                         '            )\n'
                                         '\n'
                                         '        deps = _run_deps(ctx)\n'
                                         '        if deps is not None and isinstance(result, '
                                         'dict):\n'
                                         '            result_path = result.get("path")\n'
                                         '            if isinstance(result_path, str):\n'
                                         '                '
                                         'deps.inspected_paths.add(_normalized_path(result_path))\n'
                                         '        return result\n'
                                         '    except EXPECTED_TOOL_ERRORS as error:\n'
                                         '        return _tool_error(error)\n')],
 'backend/services/pydantic_runner.py': [('        async with agent.run_stream_events(\n'
                                          '            clean_prompt,\n'
                                          '            message_history=message_history,\n'
                                          '            instructions=run_instructions or None,\n'
                                          '            deps=run_deps,\n'
                                          '            usage_limits=UsageLimits(\n'
                                          '                request_limit=self.max_model_requests,\n'
                                          '                '
                                          'tool_calls_limit=self.max_model_requests * 2,\n'
                                          '            ),\n'
                                          '        ) as events:\n',
                                          '        request_limit = '
                                          'self._request_limit_for_policy(tool_policy)\n'
                                          '\n'
                                          '        async with agent.run_stream_events(\n'
                                          '            clean_prompt,\n'
                                          '            message_history=message_history,\n'
                                          '            instructions=run_instructions or None,\n'
                                          '            deps=run_deps,\n'
                                          '            usage_limits=UsageLimits(\n'
                                          '                request_limit=request_limit,\n'
                                          '                tool_calls_limit=request_limit * 2,\n'
                                          '            ),\n'
                                          '        ) as events:\n'),
                                         ('    @staticmethod\n'
                                          '    def _build_tool_policy_instructions(tool_policy: '
                                          'ToolPolicy) -> str:\n',
                                          '    def _request_limit_for_policy(\n'
                                          '        self,\n'
                                          '        tool_policy: ToolPolicy,\n'
                                          '    ) -> int:\n'
                                          '        """Return a bounded request budget for the '
                                          'selected workflow."""\n'
                                          '\n'
                                          '        if tool_policy == "propose":\n'
                                          '            return self.max_model_requests + 8\n'
                                          '        return self.max_model_requests\n'
                                          '\n'
                                          '    @staticmethod\n'
                                          '    def _build_tool_policy_instructions(tool_policy: '
                                          'ToolPolicy) -> str:\n')]}


def validate_python(path: Path, content: str) -> None:
    if path.suffix == ".py":
        ast.parse(content, filename=str(path))


def apply(project_root: Path, payload_root: Path) -> list[str]:
    missing_payloads = [
        relative
        for relative in ADDED_FILES
        if not (payload_root / relative).is_file()
    ]
    missing_targets = [
        relative
        for relative in PATCHES
        if not (project_root / relative).is_file()
    ]
    if missing_payloads or missing_targets:
        parts = []
        if missing_payloads:
            parts.append(
                "Missing code-drop files:\n  - "
                + "\n  - ".join(missing_payloads)
            )
        if missing_targets:
            parts.append(
                "Missing project files:\n  - "
                + "\n  - ".join(missing_targets)
            )
        raise RuntimeError("\n".join(parts))

    staged: dict[Path, str] = {}
    changed: list[str] = []

    for relative in ADDED_FILES:
        source = payload_root / relative
        target = project_root / relative
        content = source.read_text(encoding="utf-8")
        validate_python(target, content)
        staged[target] = content
        if not target.exists() or target.read_text(encoding="utf-8") != content:
            changed.append(relative)

    for relative, replacements in PATCHES.items():
        target = project_root / relative
        original = target.read_text(encoding="utf-8")
        updated = original

        for old, new in replacements:
            if new in updated:
                continue
            count = updated.count(old)
            if count != 1:
                raise RuntimeError(
                    f"Refusing to patch {relative}: expected one matching "
                    f"source block, found {count}. No files were changed."
                )
            updated = updated.replace(old, new, 1)

        validate_python(target, updated)
        staged[target] = updated
        if updated != original:
            changed.append(relative)

    for target, content in staged.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(
            target.suffix + ".tool-resilience.tmp"
        )
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(target)

    return sorted(set(changed))


def main() -> int:
    project_root = (
        Path(sys.argv[1]).resolve()
        if len(sys.argv) > 1
        else Path.cwd().resolve()
    )
    payload_root = Path(__file__).resolve().parent

    try:
        changed = apply(project_root, payload_root)
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if changed:
        print("AI Lab tool-resilience drop applied:")
        for relative in changed:
            print(f"  - {relative}")
    else:
        print("The tool-resilience drop was already applied.")

    print()
    print("Focused checks:")
    print(
        "  python -m pytest -q "
        "tests/test_provider_settings_service.py "
        "tests/test_tool_call_resilience.py "
        "tests/test_pydantic_agent.py "
        "tests/test_pydantic_runner.py"
    )
    print()
    print("Full backend suite:")
    print("  python -m pytest -q")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
