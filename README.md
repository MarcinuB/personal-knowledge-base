# Personal Knowledge Base

A RAG-powered personal knowledge assistant. Upload documents into topic-scoped collections
and chat with them using a local LLM (Ollama) or OpenAI.

Built with: LangChain · LangGraph · ChromaDB · FastAPI · React · PostgreSQL · Docker

---

## Features

- **Collections** — create named knowledge spaces (Recipes, Gardening, etc.)
- **Document ingestion** — upload PDF, DOCX, or TXT files
- **RAG chat** — multi-turn conversations with history-aware query rewriting
- **Advanced retrieval** — parent-child chunking + cross-encoder reranking
- **Local or cloud LLM** — Ollama (default) or OpenAI via env var
- **Connectors** — sync documents from external sources (DummyConnector included; Google Drive, Obsidian planned)
- **Chat history** — persistent conversations with sidebar navigation

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [Ollama](https://ollama.com/) (if using local models) — or an OpenAI API key

---

## Quickstart

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/personal-knowledge-base.git
cd personal-knowledge-base

# 2. Copy and edit environment variables
cp .env.example .env

# 3. Pull required Ollama models (if using Ollama)
ollama pull llama3
ollama pull nomic-embed-text

# 4. Start all services
docker compose up --build

# 5. Open the app
open http://localhost:3000
```

---

## Environment Variables

Copy `.env.example` to `.env` and adjust as needed.

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama` or `openai` |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama service URL |
| `OLLAMA_MODEL` | `llama3` | LLM model name |
| `EMBEDDING_PROVIDER` | `ollama` | `ollama` or `openai` |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model name |
| `OPENAI_API_KEY` | `` | Required if provider is `openai` |
| `POSTGRES_URL` | `postgresql://...` | Set automatically in Docker Compose |
| `CHROMADB_HOST` | `chromadb` | ChromaDB service hostname |
| `CHROMADB_PORT` | `8001` | ChromaDB service port |

---

## Switching to OpenAI

Edit `.env`:

```env
LLM_PROVIDER=openai
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

Then restart: `docker compose up`

---

## Running Tests

```bash
# Unit tests (no infrastructure required)
docker compose run --rm backend pytest backend/app -m unit

# Integration tests (spins up real Postgres + ChromaDB via testcontainers)
docker compose run --rm backend pytest backend/app -m integration

# E2E tests (requires full stack running)
docker compose up -d
pytest backend/tests -m e2e
```

---

## Project Structure

See [docs/architecture.md](docs/architecture.md) for the full system diagram and data flow.

```
backend/app/
├── knowledge/    # Collections + document ingestion
├── chat/         # Conversations + LangGraph RAG pipeline
├── connectors/   # Data source adapters (BaseConnector + DummyConnector)
└── shared/       # LLM/embedding factories, DB, ChromaDB, config
```

---

## Architecture Decisions

See [docs/adr/](docs/adr/) for the full set of Architecture Decision Records:

- [ADR 0001](docs/adr/0001-rag-pipeline.md) — RAG pipeline strategy
- [ADR 0002](docs/adr/0002-ddd-structure.md) — DDD bounded context structure
- [ADR 0003](docs/adr/0003-storage.md) — PostgreSQL + ChromaDB storage split
- [ADR 0004](docs/adr/0004-connector-interface.md) — Connector interface design

---

## Domain Glossary

See [CONTEXT.md](CONTEXT.md) for definitions of Collection, Document, Chunk, Connector,
Conversation, Message, and other domain terms.
