# AI Lab Backend

This backend provides a small FastAPI service for:
- chat completions via Ollama
- streamed chat responses
- embeddings
- simple RAG-style context retrieval

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
OLLAMA_MODEL=qwen3:4b and qwen2.5-coder:3b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
HOST=0.0.0.0
PORT=8000
```

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
