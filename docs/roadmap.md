# Roadmap and Learning Log

## Current Phase: Embeddings and ChromaDB

Objective:

Build a small semantic search system before connecting it to the LLM.

Why:

If retrieval does not work independently, RAG will be hard to debug.

---

## Step 1: Embedding Basics

Understand:

* Why embeddings exist
* Text can be converted into vectors
* Similar meanings produce similar vectors
* Vector similarity is used for search
* Cosine similarity compares vector direction

Key idea:

Embeddings allow semantic search, not just keyword search.

Example:

Search query:

```text
spawn enemy object
```

Should retrieve documents about:

```text
Instantiate prefab
```

even if the exact words are different.

---

## Step 2: ChromaDB

Use ChromaDB locally.

Purpose:

* Store document chunks
* Store embeddings
* Store metadata
* Retrieve similar chunks

Use local persistent mode first.

No cloud.

No paid services.

No API keys.

---

## Step 3: Tiny Unity Docs Dataset

Start with a few local markdown files:

```text
unity_docs/
├── navmesh.md
├── animator.md
├── prefabs.md
├── scriptable_objects.md
├── physics.md
└── input.md
```

Do not start with 100 files.

First prove the system works with 5–6 files.

---

## Step 4: Indexing

Indexing means:

```text
Read documents
↓
Split into chunks
↓
Generate embeddings
↓
Store in ChromaDB
```

This should happen when documents are added or updated.

It should not happen on every user question.

---

## Step 5: Searching

Search means:

```text
User query
↓
Generate query embedding
↓
Compare with stored document embeddings
↓
Return top relevant chunks
```

At this stage, do not use Qwen yet.

Only verify that the correct documents are returned.

---

## Step 6: First RAG Endpoint

After search works:

```text
User question
↓
Retrieve relevant docs
↓
Build prompt with docs + question
↓
Send to Qwen
↓
Return grounded answer
```

---

## Future Phases

### Tool Calling

Allow the model to use functions such as:

* search documents
* read files
* list project files
* search codebase
* call APIs

### Memory

Add memory later.

Memory should not just mean sending the entire conversation forever.

Possible memory types:

* recent chat history
* summarized old history
* saved user/project facts
* retrieved relevant memories

### Agent

An agent is an LLM loop that can:

1. Think about the task
2. Choose a tool
3. Run the tool
4. Observe result
5. Continue or answer

Do not start with agents before understanding RAG and tools.

---

## Business/Career Notes

This project has strong learning value because it teaches durable AI engineering skills:

* backend APIs
* streaming
* local model serving
* embeddings
* vector search
* RAG
* system architecture
* future agents

The product/business value is not guaranteed.

The stronger direction is not “sell an AI agent.”

The stronger direction is:

```text
Solve a real business problem using AI as part of the system.
```

AI is the tool, not automatically the business.
