# AI Lab System Guide

## Overview

This project is a local-first AI assistant that can:

- answer general questions with a local LLM
- search through local markdown documents
- retrieve relevant document chunks
- build grounded answers using retrieval-augmented generation (RAG)
- stream responses back to the user

The basic flow is simple:

1. the user asks a question
2. the system finds relevant context
3. the model answers using that context
4. the answer is returned to the UI

---

## High-Level Architecture

The system is split into three main layers:

- Frontend: handles the chat UI
- Backend: handles API requests, AI logic, retrieval, and streaming
- Local services: Ollama for chat, embeddings, and Chroma for vector search

A simple request flow looks like this:

```text
User question
   ↓
Frontend
   ↓
FastAPI route
   ↓
RAG service
   ↓
Embedding search + document context
   ↓
Ollama model
   ↓
Answer
```

---

## Main Folders

### Frontend

The frontend is responsible for:

- showing the chat interface
- sending prompts to the backend
- displaying the response
- handling streaming output

### Backend

The backend contains the real AI logic.

Key folders:

- routes: API endpoints
- services: business logic for AI tasks
- tests: regression tests for core behavior

### Docs

The docs folder contains project notes about architecture, decisions, and planning.

---

## How a Normal Chat Request Works

When the user sends a regular chat message:

1. the frontend sends a request to the backend
2. the route validates the request
3. the backend sends the prompt to Ollama
4. Ollama generates a response
5. the response is returned to the frontend

This path is useful for general conversation and does not rely on the document database.

---

## How the Document-Based RAG Flow Works

The document workflow is more structured.

### 1. Load documents

The document loader reads markdown files from the local documents folder.

### 2. Split documents into chunks

The chunker splits each markdown file into smaller sections, usually by headings.

This is important because:

- large documents are harder to search
- smaller chunks are more focused
- retrieval becomes more accurate

### 3. Create embeddings

Each chunk is converted into a vector using an embedding model.

An embedding is a numerical representation of meaning.

That means:

- similar text produces similar vectors
- the system can search by semantic similarity, not only by exact keyword match

### 4. Store embeddings in Chroma

The vector database stores:

- the chunk text
- its embedding
- metadata such as source file and chunk index

### 5. Search for relevant chunks

When the user asks a question:

1. the question is embedded
2. Chroma searches for the closest matching chunks
3. the most relevant chunks are selected

### 6. Build a prompt with context

The retrieved chunks are inserted into a prompt.

That prompt tells the language model to:

- use the retrieved context
- answer only from that context when possible
- say when the context is not enough

### 7. Generate the answer

The model answers using the retrieved context.

This is the core RAG pattern:

- retrieve relevant information
- add it to the prompt
- let the model answer

---

## Key Backend Components

### Routes

The routes layer is thin. It should mainly:

- validate input
- call a service
- return a result

This keeps the API layer simple and makes the system easier to maintain.

### Services

The services layer contains the real logic.

Important services include:

- RAGService: orchestrates retrieval, prompting, and answer generation
- EmbeddingService: creates embeddings
- ChromaService: stores and searches vectors
- OllamaClient: handles chat, streaming, and embedding requests
- DocumentLoader: reads local markdown documents
- Chunker: splits documents into smaller chunks

---

## What the RAG Service Does

The RAG service is the heart of the document-based workflow.

It is responsible for:

- searching for relevant chunks
- building context from retrieved chunks
- creating a grounded prompt
- generating an answer
- handling fallback behavior when no good results are found

The service has two main answer modes:

- RAG mode: uses retrieved document context
- fallback mode: answers from general model knowledge when no relevant documents were found

This distinction is important because it prevents the model from pretending the documents support a claim when they do not.

---

## Why Retrieval Filtering Matters

The system uses a distance threshold to avoid weak matches.

This helps prevent the model from answering from irrelevant or low-quality context.

In other words:

- strong matches are kept
- weak matches are filtered out

This improves answer quality.

---

## Why Prompt Design Matters

Prompt design is a real part of the system.

A good prompt tells the model:

- what to use
- what not to invent
- when to be cautious
- how to answer clearly

The current prompt design tries to make the model:

- stay grounded in retrieved context
- avoid unsupported claims
- be concise
- clearly say when information is missing

---

## Streaming Behavior

The system also supports streaming responses.

Instead of waiting for the full answer, the response is sent back in chunks.

This gives the user a more interactive experience and feels more like a live assistant.

---

## Important Concepts to Understand

### Embeddings

Embeddings turn text into vectors that represent meaning.

They help the system find similar content even when the words are different.

### Chunks

Chunks are smaller pieces of text extracted from documents.

They make retrieval more precise.

### Vector Database

A vector database stores embeddings so similar content can be searched quickly.

### RAG

RAG means:

- retrieve relevant context
- add it to the prompt
- generate an answer

It is not the same as simply asking the model a question.

---

## Why This Architecture Is Helpful

This structure keeps responsibilities clear:

- routes handle requests
- services handle logic
- Ollama handles model inference
- Chroma handles vector search

That makes the project easier to:

- understand
- test
- extend
- improve later

---

## Suggested Mental Model

If you are new to the codebase, think of it like this:

- the frontend is the face
- the backend is the brain
- Ollama is the thinker
- Chroma is the memory search engine

The system works best when these pieces cooperate.

---

## Next Steps

Possible next improvements include:

- upload support for user documents
- better chunking strategies
- citations in answers
- stronger memory features
- tool calling and agent-style workflows
- better ranking and retrieval quality