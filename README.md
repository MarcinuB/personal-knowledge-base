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
git clone https://github.com/MarcinuB/personal-knowledge-base.git
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
| `LLM_MODEL` | `llama3` | LLM model name (use `OLLAMA_MODEL` for legacy compat) |
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

### Test markers

| Marker | What it tests | Dependencies |
|--------|--------------|--------------|
| `unit` | Pure logic, no I/O — fast, no external services | None |
| `integration` | Full ingestion + retrieval flow | Docker (testcontainers spins up Postgres + ChromaDB automatically) |
| `eval` | RAGAS quality scores (faithfulness, answer relevancy) | Docker + `OPENAI_API_KEY` |

### Option A — local venv (recommended for development)

Faster iteration: no container spin-up, instant feedback on unit tests.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Then run tests:

```bash
# All unit tests (no Docker needed)
pytest app -m unit

# Single file
pytest app/shared/tests/test_config.py -v

# Single class or test
pytest app/shared/tests/test_config.py::TestSettingsDefaults -v

# Integration tests (testcontainers starts Postgres + ChromaDB automatically)
pytest app -m integration

# RAGAS eval tests — run manually or nightly, not on every PR
OPENAI_API_KEY=sk-... pytest evals -m eval -v -s
```

### Option B — Docker (useful for CI or a clean environment check)

Note: paths are relative to the container's `/app` working directory, not the repo root.

```bash
# All unit tests
docker compose run --rm backend pytest app -m unit

# Single file
docker compose run --rm backend pytest app/shared/tests/test_config.py -v

# Integration tests (testcontainers spins up Postgres + ChromaDB automatically)
docker compose run --rm backend pytest app -m integration

# E2E tests (requires full stack running)
docker compose up -d
docker compose run --rm backend pytest tests -m e2e
```

### Generating the RAGAS testset

The eval testset (`backend/evals/testset.json`) is committed to the repo and used as-is by the eval tests. To regenerate it (e.g. after updating the sample document):

```bash
cd backend
OPENAI_API_KEY=sk-... python -m evals.generate_testset
# Review evals/testset.json, remove any poor-quality questions, then commit
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

---

## Troubleshooting

### ChromaDB connectivity errors

**Symptom:** Backend logs show `Connection refused` or `Failed to connect to ChromaDB` on startup.

**Cause:** The backend started before ChromaDB finished initialising. This is rare after the healthcheck was added, but can happen on very slow machines.

**Fix:** Restart the backend service:
```bash
docker compose restart backend
```

If it keeps failing, check ChromaDB health directly:
```bash
curl http://localhost:8001/api/v1/heartbeat
```

---

### Alembic migration failures

**Symptom:** Backend exits immediately with an `alembic` error, or the `/health` endpoint returns 500 shortly after `docker compose up`.

**Cause:** A previous migration left the database in an inconsistent state, or the `postgres` service wasn't fully ready before the backend started.

**Fix:** Check the backend logs for the specific error, then reset if needed:
```bash
docker compose logs backend

# Nuclear option — wipes all data and reruns migrations from scratch:
docker compose down -v && docker compose up
```

---

### Chat fails when using OpenAI

**Symptom:** Sending a chat message returns an error such as `AuthenticationError` or `Incorrect API key`.

**Cause:** `LLM_PROVIDER` is set to `openai` but `OPENAI_API_KEY` is missing or invalid in your `.env` file.

**Fix:** Add your key to `.env` (copy `.env.example` as a starting point) and restart:
```bash
echo "OPENAI_API_KEY=sk-..." >> .env
docker compose restart backend
```
