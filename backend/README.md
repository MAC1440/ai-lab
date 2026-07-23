# AI Lab Backend

This backend provides a small FastAPI service for:

- Pydantic AI and legacy agent streams through Ollama
- coding, Unity, and general agent profiles
- workspace-confined file inspection and search
- ChromaDB-backed RAG for enabled agents
- reviewable workspace file changes
- safe streamed workspace verification with persistent run history
- durable multi-file project tasks with approval, verification, and repair

## Quick start

1. Create and activate the virtual environment
2. Install dependencies
3. Start the server

```bash
pip install -r requirements.txt
python app.py
```

## Swagger UI

Once the server is running, open:
- http://127.0.0.1:8000/docs
- http://127.0.0.1:8000/redoc

## Environment variables

Copy [.env.example](.env.example) to [.env](.env) and adjust as needed.

```env
OLLAMA_BASE_URL=http://localhost:11434
PYDANTIC_AI_OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=granite4.1:3b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
VERIFICATION_DB_PATH=data/verification.sqlite3
VERIFICATION_MAX_OUTPUT_CHARS=200000
PROJECT_TASK_DB_PATH=data/project-tasks.sqlite3
RELIABILITY_BENCHMARK_DB_PATH=data/reliability-benchmarks.sqlite3
RELIABILITY_BENCHMARK_WORK_ROOT=data/reliability-workspaces
```

The current agent profile model names live in
[`services/agent_service.py`](services/agent_service.py). `OLLAMA_MODEL` is the
fallback for direct `OllamaClient` use; it does not override those profiles.

Set `UNITY_EDITOR_PATH` to the full Unity executable path to enable optional
Unity batch-mode compile checks. Projects that declare
`com.unity.test-framework` also receive an EditMode test profile whose NUnit
XML is parsed independently of Unity's process exit code.

### Durable project tasks

The **Tasks** dialog creates a bounded goal, loads its controlled execution
prompt into chat, and persists progress through proposal review, verification,
and repair. The browser sends `project_task_id` with the agent request. The
model still has no direct write or shell access: all file changes remain
validated proposals, and verification remains restricted to detected profile
IDs.

## Example endpoints

### List agents

```bash
curl http://127.0.0.1:8000/agent/list
```

### Stream a Pydantic AI agent

```bash
curl -N -X POST http://127.0.0.1:8000/agent/chat/pydantic/stream \
  -H "Content-Type: application/json" \
  -H "Accept: application/x-ndjson" \
  -d '{"agent_id":"coding","prompt":"List the workspace root","tool_policy":"inspect"}'
```

`tool_policy` may be `auto`, `inspect`, or `propose`. Use `propose` only with
the coding agent. It requires a successful file read and reviewable file-change
proposal before the run can complete. The legacy endpoint remains available at
`/agent/chat/stream`, but it does not accept enforced tool policies.

### Select a workspace

```bash
curl -X POST http://127.0.0.1:8000/workspaces/select \
  -H "Content-Type: application/json" \
  -d '{"path":"D:\\Projects\\example"}'
```

### Workspace verification

After selecting a workspace, inspect its detected checks:

```bash
curl http://127.0.0.1:8000/verifications/profiles
```

Run one of the returned profile IDs as an NDJSON stream:

```bash
curl -N -X POST http://127.0.0.1:8000/verifications/run/stream \
  -H "Content-Type: application/json" \
  -d '{"profile_id":"replace-with-detected-profile-id"}'
```

See [Workspace Verification](../docs/workspace-verification.md) for the full
event contract, safety model, Unity setup, and test commands.
