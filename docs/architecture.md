# Architecture Notes

## High-Level Architecture

Current direction:

```text
Next.js Frontend
        ↓
FastAPI Backend
        ↓
Ollama / ChromaDB / Local Tools
```

The frontend should mainly handle UI.

The backend should own AI logic.

---

## Why Separate Frontend and Backend?

Next.js should not become overloaded with:

* LLM calls
* embeddings
* vector database logic
* RAG pipelines
* memory
* agents
* file parsing
* tool execution

FastAPI is better suited for AI backend work because most AI libraries are Python-first.

---

## Current Folder Direction

```text
AI-Lab/
│
├── frontend/
│   └── Next.js app
│
├── backend/
│   ├── app.py
│   ├── requirements.txt
│   ├── routers/
│   ├── services/
│   ├── models/
│   └── chroma_db/
│
└── docs/
    ├── roadmap.md
    ├── architecture.md
    ├── learning_log.md
    ├── decisions.md
    └── mentor_notes.md
```

---

## Backend Responsibility

FastAPI backend should handle:

* Chat endpoint
* Streaming responses
* Ollama communication
* Embedding generation
* ChromaDB storage/search
* RAG orchestration
* Future tool calling
* Future memory system
* Future agent loop

---

## Services Folder

The `services/` folder should contain business/AI logic.

Examples:

```text
services/
├── ollama_service.py
├── embedding_service.py
├── chroma_service.py
├── rag_service.py
└── memory_service.py
```

Routers should stay thin.

Good route:

```text
Receive request
↓
Validate body
↓
Call service
↓
Return response
```

Bad route:

```text
Receive request
↓
Do everything inside router file
```

---

## Embeddings Architecture

Embedding flow:

```text
Document text
        ↓
nomic-embed-text
        ↓
Vector
        ↓
ChromaDB
```

Search flow:

```text
User question
        ↓
nomic-embed-text
        ↓
Question vector
        ↓
ChromaDB similarity search
        ↓
Relevant document chunks
        ↓
LLM prompt
        ↓
Answer
```

Important:

The embedding model does not answer questions.

The embedding model creates vectors.

The LLM answers questions after receiving retrieved context.

---

## RAG Principle

RAG means:

```text
Retrieve relevant information
+
Augment the prompt
+
Generate answer
```

RAG is not the same as internet access.

Internet access is a tool.

RAG is retrieval from a knowledge source.
