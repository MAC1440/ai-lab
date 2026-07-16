# Workspace Verification

Workspace Verification runs controlled local checks after AI Lab proposes and
applies a reviewed file change. It is intentionally separate from the model and
does not expose an arbitrary shell tool.

## User flow

1. Select a workspace.
2. Ask the coding or Unity agent to inspect and update a file.
3. Review and approve the proposed diff.
4. Select **Run checks** in the approval dock, or **Verify workspace** in the
   chat header.
5. Choose one of the checks detected for the active workspace.
6. Watch command output as NDJSON events arrive.
7. Review the persisted pass, fail, timeout, cancellation, or error result.
8. For a failed run, select **Ask agent to fix** to place a grounded failure
   prompt into the coding chat.

Approval and verification remain separate actions. Approving a change never
starts a command automatically.

## Detection and profiles

The backend scans the workspace root and two directory levels below it. Large
generated folders such as `.git`, `node_modules`, `.next`, `Library`, and
`Temp` are skipped.

Supported project markers and checks:

| Project | Markers | Checks |
| --- | --- | --- |
| Python | `requirements.txt`, `pyproject.toml`, `pytest.ini`, and related files | `python -m pytest -q --tb=short`, optional Ruff |
| Node.js | `package.json` | Declared `test`, `lint`, `typecheck`, and `build` scripts |
| .NET | `.sln` or `.csproj` | `dotnet test --nologo` |
| Unity | `Assets` and `ProjectSettings/ProjectVersion.txt` | Optional Unity batch-mode compile check |

Profiles have stable generated IDs. The frontend sends only a profile ID. The
backend detects the workspace again and resolves that ID to a command from its
own catalog, so neither the browser nor the model can substitute an arbitrary
command.

## API

### Inspect the active workspace

```http
GET /verifications/profiles
```

Returns detected projects and available or unavailable profiles. Unavailable
profiles include a reason such as a missing executable.

### Stream a run

```http
POST /verifications/run/stream
Content-Type: application/json
Accept: application/x-ndjson

{
  "profile_id": "python-pytest-...",
  "proposal_id": "optional-change-proposal-id"
}
```

The stream can include:

- `verification_started`
- `command_started`
- `output`
- `command_finished`
- `verification_done`
- `error`

A successfully started run finishes with exactly one `verification_done`
event. A request rejected before a run starts finishes with an `error` event.

### History and cancellation

```http
GET  /verifications/runs?limit=20
GET  /verifications/runs/{run_id}
POST /verifications/runs/{run_id}/cancel
```

History is filtered to the active workspace.

## Agent repair contract

**Ask agent to fix** is available only for a completed check whose command
exited with a failure. Runner errors, cancellations, and timeouts need an
environment or command investigation rather than an automatic code proposal.

The frontend loads the complete persisted output for the selected run, keeps a
bounded beginning-and-end excerpt for model context, switches to the coding
agent, and starts the request without unrelated chat history. It sends
`tool_policy: "propose"` to:

```http
POST /agent/chat/pydantic/stream
```

The backend enforces that contract with per-run state and a Pydantic AI output
validator. A repair run must read a target file and successfully call
`propose_file_change`; a text-only answer is rejected and retried within the
configured model request limit. The proposal remains review-only. The user must
still approve it and run verification again before the issue can be considered
fixed.

## Persistence

Run metadata and capped output are stored in SQLite. The default path is:

```text
backend/data/verification.sqlite3
```

The `backend/data` directory is ignored by Git. If the backend stops during a
run, that stale `running` record becomes an `error` record the next time the
store initializes.

Configuration:

```env
VERIFICATION_DB_PATH=data/verification.sqlite3
VERIFICATION_MAX_OUTPUT_CHARS=200000
```

Relative database paths are resolved from the backend directory.

## Unity setup

Unity verification is offered only when `UNITY_EDITOR_PATH` points to a real
Unity executable.

Example on Windows:

```env
UNITY_EDITOR_PATH=C:\Program Files\Unity\Hub\Editor\6000.0.0f1\Editor\Unity.exe
```

Close the Unity Editor before running the batch-mode check. Unity normally
locks an open project, and the verification command should fail visibly rather
than trying to bypass that lock.

## Safety boundaries

- Commands use argument arrays and `shell=False` behavior.
- The browser sends profile IDs, not command strings.
- The model cannot call the verification service as a tool.
- Commands run inside a verified child of the selected workspace.
- Only a reduced environment is passed to child processes.
- Output and execution time are capped.
- One run may execute per workspace at a time.
- Closing the stream or selecting cancel terminates the process tree.
- Verification never approves another file change.

This is application-level command confinement, not a full operating-system
sandbox. Checks should still be limited to projects and scripts the user
trusts. In particular, `npm run` executes scripts stored in the selected
project's `package.json`.

## Validation

Backend focused tests:

```powershell
cd backend
python -m pytest -q `
  tests/test_project_detection_service.py `
  tests/test_verification_store.py `
  tests/test_verification_service.py
```

Frontend validation:

```powershell
cd frontend
npm run lint
npm run build
```

To check only the files involved in this module while iterating:

```powershell
npx eslint features/verification `
  features/home/components/chat-panel.tsx `
  features/changes/change-proposal-dock.tsx
```
