# AI Lab Backend

This backend provides a small FastAPI service for:
- chat completions via Ollama
- streamed chat responses
- embeddings
- simple RAG-style context retrieval
- reviewable workspace file changes
- safe streamed workspace verification with persistent run history

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
OLLAMA_MODEL=granite4.1:3b and qwen2.5-coder:3b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
HOST=0.0.0.0
PORT=8000
VERIFICATION_DB_PATH=data/verification.sqlite3
VERIFICATION_MAX_OUTPUT_CHARS=200000
```

Set `UNITY_EDITOR_PATH` to the full Unity executable path to enable optional
Unity batch-mode checks.

## Example endpoints

### Chat

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Explain RAG","use_rag":true,"documents":["RAG retrieves relevant context before answering."]}'
```

### Stream chat

```bash
curl -N -X POST http://127.0.0.1:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Write a short summary"}'
```

### Embed

```bash
curl -X POST http://127.0.0.1:8000/embed \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello world"}'
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
