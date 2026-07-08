# AI-Lab Project Notes

## Project Goal

Build a personal AI engineering platform that can run locally and eventually support:

* Local LLM chat
* FastAPI backend
* Next.js frontend
* Streaming responses
* Embeddings
* ChromaDB vector search
* RAG over documents
* Tool calling
* Memory
* Agents
* Possible Unity assistant integration

The goal is not only to build a chatbot, but to understand the full AI application stack.

---

## Current Stack

### Frontend

* Next.js
* Radix UI
* Streaming chat UI
* Model settings panel
* Conversation history
* LLM performance metrics

### Backend

* Python
* FastAPI
* Pydantic
* Swagger/OpenAPI
* Streaming endpoints
* Ollama integration

### Local AI

* Ollama
* Chat model: `qwen3:4b or qwen2.5-coder:3b`
* Embedding model: `nomic-embed-text`

### Vector Database

* ChromaDB, planned for local persistent storage

---

## Current Progress

Completed:

* Local LLM running through Ollama
* Next.js frontend connected to local LLM
* FastAPI backend created
* Streaming response flow working
* Pydantic models added
* Swagger running
* Basic model options exposed
* Embedding model downloaded
* ChromaDB installation started

Current focus:

* Understand embeddings
* Store document embeddings in ChromaDB
* Retrieve relevant documents through semantic search
* Later connect retrieved documents to the LLM for RAG

---

## Learning Philosophy

Do not only copy AI-generated code.

For every feature, understand:

1. What problem it solves
2. Where it lives architecturally
3. What input it receives
4. What output it returns
5. How to debug it independently

Preferred learning style:

* Build step by step
* Understand concepts through implementation
* Use AI help, but do not blindly trust generated code
* Prefer durable engineering knowledge over hype

---

## Mentor Preferences

When discussing project ideas or career moves:

* Be honest, not overly supportive
* Evaluate whether the idea is worth doing
* Consider earning potential and business value
* Consider long-term market relevance
* Use current trends when needed
* Point out opportunity cost
* Explain tradeoffs clearly

The goal is mentorship, not motivation alone.
