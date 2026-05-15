# System Architecture

## Overview

Personal Knowledge Base is a RAG-powered chatbot system. Users upload documents into
topic-scoped Collections, then chat with those collections. The LLM answers only from
retrieved document context; if no relevant context is found, it says so.

---

## Services

```
┌─────────────────────────────────────────────────────────┐
│                     Docker Compose                       │
│                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐  │
│  │ frontend │    │ backend  │    │     ollama        │  │
│  │  :3000   │───►│  :8000   │───►│ LLM + embeddings  │  │
│  │  React   │    │ FastAPI  │    │  nomic-embed-text │  │
│  └──────────┘    └────┬─────┘    └──────────────────┘  │
│                       │                                  │
│              ┌────────┴────────┐                        │
│              ▼                 ▼                        │
│        ┌──────────┐    ┌──────────────┐                │
│        │ chromadb │    │  postgres    │                 │
│        │  :8001   │    │   :5432      │                 │
│        │ vectors  │    │ chat history │                 │
│        └──────────┘    └──────────────┘                │
└─────────────────────────────────────────────────────────┘
```

---

## Backend Domain Structure

```
backend/app/
├── knowledge/     # Collection CRUD, document ingestion, chunking
├── chat/          # Conversations, messages, RAG pipeline (LangGraph)
├── connectors/    # BaseConnector interface, DummyConnector, sync
└── shared/        # LLM/embedding factories, DB, ChromaDB, config
```

Each domain owns its own models, schemas, service, routes, and tests.
Domains communicate only through their public service interfaces — never by
importing each other's internal models directly.

---

## Ingestion Path

```
User uploads file (PDF/DOCX/TXT)
        │
        ▼
knowledge/service.py
  1. Parse document (LangChain loaders)
  2. Split into Parent Chunks (RecursiveCharacterTextSplitter, large)
  3. Split Parents into Child Chunks (small, for embedding)
  4. Embed Child Chunks (nomic-embed-text via Ollama)
  5. Store in ChromaDB:
     - Child Chunk + embedding + parent_id metadata
     - Parent Chunk stored as a separate docstore
  6. Record Document metadata in PostgreSQL
```

---

## Query Path

```
User sends message
        │
        ▼
LangGraph state machine (chat/graph.py)
  ┌─── collection_router ──────────────────────────────────┐
  │    Check available collections; ask user to pick one   │
  │    → if no match: early exit with "I don't know"       │
  └────────────────────────────────────────────────────────┘
        │
        ▼
  ┌─── query_rewriter ─────────────────────────────────────┐
  │    Rewrite follow-up using conversation history        │
  │    (create_history_aware_retriever)                    │
  └────────────────────────────────────────────────────────┘
        │
        ▼
  ┌─── retriever ──────────────────────────────────────────┐
  │    ParentDocumentRetriever:                            │
  │    - Embed rewritten query                             │
  │    - Search child chunks in ChromaDB (top-20)         │
  │    - Expand to parent chunks                           │
  └────────────────────────────────────────────────────────┘
        │
        ▼
  ┌─── reranker ───────────────────────────────────────────┐
  │    cross-encoder/ms-marco-MiniLM                       │
  │    Re-score parent chunks, keep top-5                  │
  └────────────────────────────────────────────────────────┘
        │
        ▼
  ┌─── generator ──────────────────────────────────────────┐
  │    LLM (Ollama llama3 or OpenAI gpt-4o-mini)          │
  │    Prompt: top-5 chunks + conversation history        │
  │    Stream tokens via SSE to frontend                  │
  └────────────────────────────────────────────────────────┘
```

---

## LLM Configuration

The system supports two LLM providers, switchable via environment variables:

| Env Var | Default | Options |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama`, `openai` |
| `OLLAMA_MODEL` | `llama3` | any model pulled in Ollama |
| `EMBEDDING_PROVIDER` | `ollama` | `ollama`, `openai` |
| `EMBEDDING_MODEL` | `nomic-embed-text` | any embedding model |
| `OPENAI_API_KEY` | `` | required if provider is `openai` |

---

## Data Storage

| Data | Store | Why |
|---|---|---|
| Document vectors + child chunks | ChromaDB | Purpose-built for ANN search |
| Parent chunk docstore | ChromaDB (metadata) | Co-located with child chunks |
| Collection metadata | PostgreSQL | Relational, queryable |
| Conversations + Messages | PostgreSQL | Relational, foreign-keyed |
| Connector sync status | PostgreSQL | Fits existing schema |
