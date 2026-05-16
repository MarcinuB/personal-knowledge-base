#!/usr/bin/env bash
# Usage: GITHUB_TOKEN=ghp_xxx bash scripts/create_github_issues.sh
set -euo pipefail

REPO="MarcinuB/personal-knowledge-base"
API="https://api.github.com/repos/${REPO}/issues"
AUTH="Authorization: Bearer ${GITHUB_TOKEN}"

create_issue() {
  local title="$1"
  local body="$2"
  local labels="$3"
  echo "Creating: $title"
  curl -s -X POST "$API" \
    -H "$AUTH" \
    -H "Content-Type: application/json" \
    -d "$(jq -n --arg t "$title" --arg b "$body" --argjson l "$labels" \
      '{title: $t, body: $b, labels: $l}')" \
    | jq -r '.html_url'
}

# ---------------------------------------------------------------------------
# PHASE 1 — Foundation
# ---------------------------------------------------------------------------

create_issue \
"[Phase 1] Shared configuration with pydantic-settings" \
'## Context
All backend services (LLM, embeddings, DB, ChromaDB) need configuration driven by environment variables so the system works with both Ollama and OpenAI without code changes.

## File to create
`backend/app/shared/config.py`

## Requirements
- Use `pydantic-settings` (`BaseSettings`) to read env vars with defaults
- Include all settings below with the exact field names shown:

```python
class Settings(BaseSettings):
    llm_provider: Literal["ollama", "openai"] = "ollama"
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3"
    openai_api_key: str = ""
    embedding_provider: Literal["ollama", "openai"] = "ollama"
    embedding_model: str = "nomic-embed-text"
    postgres_url: str = "postgresql+asyncpg://pkb:pkb@postgres:5432/pkb"
    chromadb_host: str = "chromadb"
    chromadb_port: int = 8001

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

- Expose a cached singleton: `def get_settings() -> Settings`
- Use `@lru_cache` so settings are only read once per process

## Dependencies
None — this is the first piece of shared infrastructure.

## Tests
`backend/app/shared/tests/test_config.py`
- Test that defaults are correct
- Test that env var overrides work (monkeypatch `os.environ`)

## Acceptance criteria
- `from app.shared.config import get_settings; s = get_settings()` works
- All fields have correct types and defaults
- Tests pass with `pytest -m unit`' \
'["phase-1","foundation","backend"]'

# ---------------------------------------------------------------------------

create_issue \
"[Phase 1] PostgreSQL connection, SQLAlchemy async engine, and Alembic migrations" \
'## Context
Chat history (conversations + messages) and collection metadata are stored in PostgreSQL. We need an async SQLAlchemy engine and an Alembic migration setup so the schema is versioned.

## Files to create
- `backend/app/shared/database.py` — engine + session factory
- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/versions/` (empty, populated by future migrations)

## Requirements

### `database.py`
```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

def get_engine(settings: Settings) -> AsyncEngine: ...
def get_session_factory(engine) -> async_sessionmaker[AsyncSession]: ...

# FastAPI dependency
async def get_db() -> AsyncIterator[AsyncSession]: ...
```

### Alembic
- Use async migrations (`asyncio` mode in `env.py`)
- `target_metadata = Base.metadata` so `alembic revision --autogenerate` picks up models
- Connection string read from `settings.postgres_url`

## Dependencies
- `[Phase 1] Shared configuration` must be done first

## Tests
`backend/app/shared/tests/test_database.py`
- Integration test: use `testcontainers` to spin up a real Postgres container
- Test that `get_db()` yields a working session
- Mark with `@pytest.mark.integration`

## Acceptance criteria
- `alembic upgrade head` runs without error against a real Postgres
- `get_db()` dependency yields a working `AsyncSession`
- Integration test passes with `pytest -m integration`' \
'["phase-1","foundation","backend","database"]'

# ---------------------------------------------------------------------------

create_issue \
"[Phase 1] ChromaDB client singleton" \
'## Context
Both the knowledge domain (storing chunks) and the chat domain (querying chunks) need access to a shared ChromaDB client. We centralise it in `shared/` to avoid creating multiple connections.

## File to create
`backend/app/shared/chromadb.py`

## Requirements
```python
import chromadb
from functools import lru_cache
from app.shared.config import get_settings

@lru_cache(maxsize=1)
def get_chroma_client() -> chromadb.AsyncHttpClient:
    settings = get_settings()
    return chromadb.AsyncHttpClient(
        host=settings.chromadb_host,
        port=settings.chromadb_port,
    )
```

- Use `chromadb.AsyncHttpClient` (not the in-memory client) so it works against the Docker service
- Expose `get_chroma_client()` as a FastAPI dependency and a direct import

## Dependencies
- `[Phase 1] Shared configuration` must be done first

## Tests
`backend/app/shared/tests/test_chromadb.py`
- Unit test: mock the HTTP client and verify `get_chroma_client()` returns the same instance on repeated calls (lru_cache)
- Integration test: spin up ChromaDB via testcontainers (or connect to the Docker service) and verify `heartbeat()` succeeds
- Mark integration test with `@pytest.mark.integration`

## Acceptance criteria
- `get_chroma_client()` returns a singleton
- Client connects to ChromaDB Docker service on configured host/port' \
'["phase-1","foundation","backend"]'

# ---------------------------------------------------------------------------

create_issue \
"[Phase 1] LLM and embedding factories (Ollama + OpenAI)" \
'## Context
The chat pipeline needs a LangChain LLM object and the ingestion pipeline needs a LangChain embeddings object. Both must be switchable between Ollama and OpenAI via a single env var (`LLM_PROVIDER` / `EMBEDDING_PROVIDER`).

## Files to create
- `backend/app/shared/llm.py`
- `backend/app/shared/embeddings.py`

## Requirements

### `llm.py`
```python
from langchain_core.language_models import BaseChatModel
from app.shared.config import Settings

def get_llm(settings: Settings) -> BaseChatModel:
    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=settings.ollama_model, api_key=settings.openai_api_key)
    else:
        from langchain_ollama import ChatOllama
        return ChatOllama(model=settings.ollama_model, base_url=settings.ollama_base_url)
```

### `embeddings.py`
```python
from langchain_core.embeddings import Embeddings
from app.shared.config import Settings

def get_embeddings(settings: Settings) -> Embeddings:
    if settings.embedding_provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model=settings.embedding_model, api_key=settings.openai_api_key)
    else:
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(model=settings.embedding_model, base_url=settings.ollama_base_url)
```

## Dependencies
- `[Phase 1] Shared configuration` must be done first

## Tests
`backend/app/shared/tests/test_llm.py`, `test_embeddings.py`
- Unit test: mock provider imports, verify correct class is returned for each provider value
- Test that `ValueError` is raised for unknown provider values

## Acceptance criteria
- `get_llm(settings)` returns a `BaseChatModel` for both providers
- `get_embeddings(settings)` returns an `Embeddings` for both providers
- Switching `LLM_PROVIDER=openai` + valid key produces an OpenAI client' \
'["phase-1","foundation","backend"]'

# ---------------------------------------------------------------------------

create_issue \
"[Phase 1] FastAPI app entrypoint, Dockerfile, and health endpoint" \
'## Context
We need the FastAPI application shell that all domain routers will be registered into, plus a health endpoint so Docker Compose healthchecks work, plus the backend Dockerfile.

## Files to create
- `backend/app/main.py`
- `backend/Dockerfile`
- `backend/pyproject.toml`

## Requirements

### `main.py`
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Personal Knowledge Base API", version="0.1.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)

@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
```
- Domain routers will be included here in later phases (leave commented placeholders)
- Use `lifespan` context manager to run DB migrations on startup

### `pyproject.toml` — key dependencies:
```
fastapi, uvicorn[standard], pydantic-settings,
sqlalchemy[asyncio], asyncpg, alembic,
langchain, langchain-core, langchain-ollama, langchain-openai, langchain-community,
langgraph, chromadb, sentence-transformers,
pypdf, python-docx,
pytest, pytest-asyncio, testcontainers, httpx
```

### `Dockerfile`
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install .
COPY app/ app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

## Dependencies
- All other Phase 1 issues should be done first (or in parallel)

## Acceptance criteria
- `docker compose up backend` starts without error
- `GET /health` returns `{"status": "ok"}`
- `GET /docs` shows the FastAPI Swagger UI' \
'["phase-1","foundation","backend","docker"]'

# ---------------------------------------------------------------------------
# PHASE 2 — Knowledge domain
# ---------------------------------------------------------------------------

create_issue \
"[Phase 2] Collection CRUD — models, schemas, service, and routes" \
'## Context
A Collection is the top-level organisational unit (e.g. "Recipes", "Gardening"). Users create and manage collections. Each collection maps to a ChromaDB collection and has metadata in PostgreSQL.

See `CONTEXT.md` for the domain definition of **Collection**.

## Files to create
- `backend/app/knowledge/models.py`
- `backend/app/knowledge/schemas.py`
- `backend/app/knowledge/service.py`
- `backend/app/knowledge/router.py`
- `backend/alembic/versions/xxxx_create_collections.py`

## Requirements

### `models.py`
```python
class Collection(Base):
    __tablename__ = "collections"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)
    description: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    documents: Mapped[list["Document"]] = relationship(back_populates="collection")
```

### `schemas.py`
- `CollectionCreate(name, description)` — request
- `CollectionRead(id, name, description, created_at, document_count)` — response

### `service.py`
- `create_collection(db, data)` → creates Postgres row AND ChromaDB collection
- `list_collections(db)` → returns all collections with document count
- `get_collection(db, id)` → single collection or 404
- `delete_collection(db, id)` → deletes from Postgres AND ChromaDB

### `router.py`
```
POST   /collections
GET    /collections
GET    /collections/{id}
DELETE /collections/{id}
```
- Register in `app/main.py` with prefix `/api`

## Dependencies
- `[Phase 1] PostgreSQL connection` must be done first
- `[Phase 1] ChromaDB client` must be done first

## Tests
`backend/app/knowledge/tests/test_collection_service.py`
- Unit: mock DB + ChromaDB, test CRUD logic
- Integration: use testcontainers, test real Postgres + ChromaDB
- Mark unit with `@pytest.mark.unit`, integration with `@pytest.mark.integration`

## Acceptance criteria
- `POST /api/collections` creates a collection in both Postgres and ChromaDB
- `DELETE /api/collections/{id}` cleans up both stores
- All tests pass' \
'["phase-2","knowledge","backend"]'

# ---------------------------------------------------------------------------

create_issue \
"[Phase 2] Document model and file ingestion pipeline (PDF, DOCX, TXT)" \
'## Context
Users upload files into a Collection. The ingestion pipeline parses the file, splits it into parent and child chunks, embeds the child chunks, and stores everything in ChromaDB. See `docs/architecture.md` for the full ingestion path and `docs/adr/0001-rag-pipeline.md` for why parent-child chunking was chosen.

## Files to create
- `backend/app/knowledge/models.py` — add `Document` model (extend file from collection issue)
- `backend/app/knowledge/chunker.py`
- Update `backend/app/knowledge/service.py` — add `ingest_document()`
- Update `backend/app/knowledge/router.py` — add upload endpoint
- `backend/alembic/versions/xxxx_create_documents.py`

## Requirements

### `Document` model
```python
class Document(Base):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collections.id"))
    filename: Mapped[str]
    source_type: Mapped[str]  # "upload" | "connector"
    status: Mapped[str] = mapped_column(default="processing")  # processing | ready | failed
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    collection: Mapped["Collection"] = relationship(back_populates="documents")
```

### `chunker.py`
Use LangChain `ParentDocumentRetriever` pattern:
```python
CHILD_CHUNK_SIZE = 200   # tokens — used for embedding + search
PARENT_CHUNK_SIZE = 800  # tokens — returned to LLM as context

def build_retrievers(chroma_client, collection_name: str, embeddings):
    """Return (parent_splitter, child_splitter, vectorstore, docstore)"""
    ...
```
- Child chunks stored in ChromaDB with metadata: `{parent_id, collection_id, doc_id}`
- Parent chunks stored in ChromaDB metadata field `parent_text` (keyed by `parent_id`)

### Ingestion flow in `service.py`
```
ingest_document(db, collection_id, file_bytes, filename, content_type):
  1. Create Document row (status=processing)
  2. Parse file:
     - PDF  → LangChain PyPDFLoader
     - DOCX → LangChain Docx2txtLoader
     - TXT  → LangChain TextLoader
  3. Split into parent chunks
  4. Split parents into child chunks
  5. Embed child chunks via get_embeddings()
  6. Store child chunks + parent metadata in ChromaDB
  7. Update Document row (status=ready)
```

### Router endpoint
```
POST /api/collections/{collection_id}/documents
```
- Accept `multipart/form-data` with a single file field
- Return `DocumentRead(id, filename, status)`

## Dependencies
- `[Phase 2] Collection CRUD` must be done first
- `[Phase 1] ChromaDB client` and `[Phase 1] LLM/embedding factories` must be done first

## Tests
- Unit: mock file parsing + ChromaDB, test chunking logic in isolation
- Integration: ingest a real tiny PDF/TXT into a real ChromaDB, verify chunks exist

## Acceptance criteria
- `POST /api/collections/{id}/documents` with a PDF returns `status: ready`
- ChromaDB collection contains child chunks with correct `parent_id` metadata
- All tests pass' \
'["phase-2","knowledge","backend","rag"]'

# ---------------------------------------------------------------------------
# PHASE 3 — Chat domain
# ---------------------------------------------------------------------------

create_issue \
"[Phase 3] Conversation and Message persistence (models, schemas, service, routes)" \
'## Context
Each chat session is a Conversation scoped to one Collection. It contains an ordered list of Messages. This data is stored in PostgreSQL and displayed in the frontend sidebar.

See `CONTEXT.md` for definitions of **Conversation** and **Message**.

## Files to create
- `backend/app/chat/models.py`
- `backend/app/chat/schemas.py`
- `backend/app/chat/service.py` — persistence only (no RAG logic)
- `backend/app/chat/router.py` — conversation management routes
- `backend/alembic/versions/xxxx_create_conversations.py`

## Requirements

### `models.py`
```python
class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collections.id"))
    title: Mapped[str | None]  # auto-generated from first message
    created_at: Mapped[datetime]
    messages: Mapped[list["Message"]] = relationship(order_by="Message.created_at")

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"))
    role: Mapped[str]   # "user" | "assistant"
    content: Mapped[str]
    created_at: Mapped[datetime]
```

### Routes
```
POST   /api/conversations                    — create conversation (requires collection_id)
GET    /api/conversations                    — list all (for sidebar)
GET    /api/conversations/{id}               — get with messages
DELETE /api/conversations/{id}
```

## Dependencies
- `[Phase 2] Collection CRUD` must be done first (FK constraint)
- `[Phase 1] PostgreSQL connection` must be done first

## Tests
- Unit + integration tests in `backend/app/chat/tests/`
- Test that listing conversations returns them in reverse-chronological order

## Acceptance criteria
- `GET /api/conversations` returns list suitable for the sidebar
- Messages are ordered by `created_at` ascending within a conversation' \
'["phase-3","chat","backend","database"]'

# ---------------------------------------------------------------------------

create_issue \
"[Phase 3] LangGraph RAG pipeline — collection router, query rewriter, retriever, reranker, generator" \
'## Context
This is the core of the project. A LangGraph state machine handles the full RAG pipeline from collection selection through to streaming the LLM answer.

See `docs/architecture.md` (Query Path section) and `docs/adr/0001-rag-pipeline.md` for the full pipeline design.

## Files to create
- `backend/app/chat/graph.py` — LangGraph state + nodes + edges
- `backend/app/chat/reranker.py` — cross-encoder reranker step

## Graph State
```python
class ChatState(TypedDict):
    collection_id: str
    conversation_id: str
    user_message: str
    rewritten_query: str
    retrieved_chunks: list[Document]
    reranked_chunks: list[Document]
    messages: list[BaseMessage]   # full conversation history
    answer: str
    early_exit: bool              # True if collection not found / no context
```

## Nodes (in order)

### 1. `collection_router`
- Load available collections from Postgres
- If `collection_id` is not set, format a prompt asking user to pick ("I have: Recipes, Gardening — which would you like?")
- If collection is unknown/empty: set `early_exit=True`, return "I don'\''t have any knowledge about that topic"
- This node gates all subsequent nodes

### 2. `query_rewriter`
- Use `create_history_aware_retriever` pattern from LangChain
- Take `messages` history + `user_message`, produce `rewritten_query`
- If first message in conversation, `rewritten_query = user_message` (skip LLM call)

### 3. `retriever`
- Use `ParentDocumentRetriever` against the selected ChromaDB collection
- Retrieve top-20 child chunks, expand to parent chunks
- Store in `retrieved_chunks`

### 4. `reranker` (`reranker.py`)
- Load `cross-encoder/ms-marco-MiniLM-L-6-v2` via `sentence_transformers`
- Score each `(rewritten_query, chunk.page_content)` pair
- Keep top-5, store in `reranked_chunks`
- Cache the model with `@lru_cache`

### 5. `generator`
- Build prompt: system message with top-5 chunks + conversation history + user message
- Stream tokens from LLM via `astream()`
- System prompt must include: "Answer only from the provided context. If the context does not contain the answer, say so."

## Edges
```
START → collection_router → (early_exit?) → END
                          → query_rewriter → retriever → reranker → generator → END
```

## Dependencies
- `[Phase 3] Conversation persistence` must be done first
- `[Phase 2] Document ingestion` must be done first (need actual chunks to retrieve)
- `[Phase 1] LLM/embedding factories` must be done first

## Tests
`backend/app/chat/tests/test_graph.py`
- Unit: mock LLM + ChromaDB + Postgres, test each node in isolation
- Integration: ingest a real document, run the full graph, verify answer contains relevant content
- Test the early_exit path (unknown collection)
- Test multi-turn: second question uses rewritten query, not raw follow-up

## Acceptance criteria
- Full pipeline runs end-to-end in integration test
- Reranker re-orders chunks (verify score ordering)
- "I don'\''t know" path triggers when collection is empty' \
'["phase-3","chat","backend","rag","langgraph"]'

# ---------------------------------------------------------------------------

create_issue \
"[Phase 3] Streaming chat endpoint (SSE) and message persistence" \
'## Context
The frontend ChatWindow connects to a Server-Sent Events (SSE) endpoint that streams LLM tokens as they are generated. After streaming completes, the full message is persisted to PostgreSQL.

## Files to modify/create
- `backend/app/chat/router.py` — add `/chat` endpoint

## Requirements

### Endpoint
```
POST /api/chat
Body: { conversation_id: uuid, message: str }
Response: text/event-stream (SSE)
```

### SSE format
Each event:
```
data: {"type": "token", "content": "Hello"}\n\n
```
Final event:
```
data: {"type": "done", "conversation_id": "...", "message_id": "..."}\n\n
```
Error event:
```
data: {"type": "error", "content": "..."}\n\n
```

### Flow
1. Load conversation from DB (to get `collection_id` and message history)
2. Persist user message immediately (so it'\''s saved even if streaming fails)
3. Run LangGraph pipeline with `astream_events()`
4. Yield each token as an SSE event
5. After stream ends, persist full assistant message to DB
6. Send `done` event

### FastAPI SSE
Use `fastapi.responses.StreamingResponse` with `media_type="text/event-stream"`.
Set headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`.

## Dependencies
- `[Phase 3] LangGraph RAG pipeline` must be done first
- `[Phase 3] Conversation persistence` must be done first

## Tests
- Unit: mock LangGraph pipeline, test SSE event format
- Integration: POST to `/api/chat`, collect all SSE events, verify token stream and done event

## Acceptance criteria
- Streaming tokens appear progressively in integration test
- Assistant message is persisted to DB after stream completes
- Error during streaming sends `error` event, does not crash the server' \
'["phase-3","chat","backend","api"]'

# ---------------------------------------------------------------------------
# PHASE 4 — Connectors domain
# ---------------------------------------------------------------------------

create_issue \
"[Phase 4] BaseConnector ABC, ConnectorConfig, and ConnectorService" \
'## Context
Connectors pull documents from external sources (Google Drive, Obsidian, etc.) into a Collection. The interface must be extensible: adding a new connector should require implementing exactly two methods. See `docs/adr/0004-connector-interface.md` for the design rationale.

## Files to create
- `backend/app/connectors/base.py`
- `backend/app/connectors/service.py`
- `backend/app/connectors/router.py`

## Requirements

### `base.py`
```python
from abc import ABC, abstractmethod
from typing import AsyncIterator
from pydantic import BaseModel
from langchain_core.documents import Document

class ConnectorConfig(BaseModel):
    name: str
    source_type: str          # "dummy" | "google_drive" | "obsidian"
    collection_id: str        # target collection UUID
    settings: dict            # source-specific config (credentials, paths, etc.)

class BaseConnector(ABC):
    def __init__(self, config: ConnectorConfig):
        self.config = config

    @abstractmethod
    async def sync(self) -> AsyncIterator[Document]:
        """Yield LangChain Documents one by one."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the source is reachable."""
        ...

    @property
    def name(self) -> str:
        return self.config.name
```

### `service.py` — `ConnectorService`
- `register(connector: BaseConnector)` — add to in-memory registry
- `list_connectors()` — return all registered connectors
- `sync(connector_name: str)` — call `connector.sync()`, pass each Document to `knowledge.service.ingest_document()`
- Track `last_synced_at` per connector in PostgreSQL

### `router.py`
```
GET  /api/connectors            — list registered connectors with last_synced_at
POST /api/connectors/{name}/sync — trigger manual sync, return {documents_ingested: N}
GET  /api/connectors/{name}/health — call health_check()
```

## Dependencies
- `[Phase 2] Document ingestion pipeline` must be done first (sync calls ingest)
- `[Phase 1] PostgreSQL connection` must be done first

## Tests
- Unit: mock `sync()` generator, verify `ConnectorService` calls ingest for each document
- Verify that registering a second connector with the same name raises an error

## Acceptance criteria
- `ConnectorService.sync("dummy")` ingests all DummyConnector documents into the target collection
- `GET /api/connectors` lists connectors with correct `last_synced_at`' \
'["phase-4","connectors","backend"]'

# ---------------------------------------------------------------------------

create_issue \
"[Phase 4] DummyConnector implementation" \
'## Context
The DummyConnector is the first concrete connector. It returns hardcoded documents so the connector infrastructure can be tested end-to-end without any external API. It also serves as a reference implementation for future connectors (Google Drive, Obsidian).

## File to create
`backend/app/connectors/dummy.py`

## Requirements
```python
from langchain_core.documents import Document
from app.connectors.base import BaseConnector, ConnectorConfig

DUMMY_DOCUMENTS = [
    Document(
        page_content="Spaghetti Carbonara: Cook spaghetti al dente. Fry guanciale until crispy. Mix eggs, pecorino, black pepper. Combine off heat.",
        metadata={"source": "dummy", "title": "Spaghetti Carbonara", "category": "pasta"}
    ),
    Document(
        page_content="Tomato plants need full sun (6-8 hours/day), consistent watering, and well-drained soil with pH 6.0-6.8.",
        metadata={"source": "dummy", "title": "Growing Tomatoes", "category": "vegetables"}
    ),
    Document(
        page_content="Sourdough starter: mix 50g flour + 50g water daily for 7 days until bubbly and doubled in size.",
        metadata={"source": "dummy", "title": "Sourdough Starter", "category": "bread"}
    ),
    Document(
        page_content="Basil grows best in warm (21-29°C) conditions. Pinch flowers to keep leaves growing. Harvest in the morning.",
        metadata={"source": "dummy", "title": "Growing Basil", "category": "herbs"}
    ),
    Document(
        page_content="Risotto: toast arborio rice in butter, add warm stock ladle by ladle, stir constantly for 18 minutes.",
        metadata={"source": "dummy", "title": "Classic Risotto", "category": "rice"}
    ),
]

class DummyConnector(BaseConnector):
    async def sync(self) -> AsyncIterator[Document]:
        for doc in DUMMY_DOCUMENTS:
            yield doc

    async def health_check(self) -> bool:
        return True  # always available
```

- Register `DummyConnector` in `app/main.py` on startup for a default collection (configurable via env var `DUMMY_CONNECTOR_COLLECTION_ID`)

## Dependencies
- `[Phase 4] BaseConnector ABC` must be done first

## Tests
`backend/app/connectors/tests/test_dummy_connector.py`
- Test that `sync()` yields exactly 5 documents
- Test that `health_check()` returns `True`
- Test that all documents have `source: dummy` in metadata

## Acceptance criteria
- `POST /api/connectors/dummy/sync` returns `{documents_ingested: 5}`
- Documents appear in ChromaDB after sync
- All unit tests pass' \
'["phase-4","connectors","backend"]'

# ---------------------------------------------------------------------------
# PHASE 5 — Frontend
# ---------------------------------------------------------------------------

create_issue \
"[Phase 5] React + TypeScript frontend scaffold with Vite and typed API client" \
'## Context
The frontend is a React + TypeScript single-page application built with Vite. It communicates with the FastAPI backend. This issue covers the project scaffold and the typed API client that all components will use.

## Files to create
- `frontend/package.json`
- `frontend/vite.config.ts`
- `frontend/tsconfig.json`
- `frontend/src/api/client.ts`
- `frontend/src/api/types.ts`
- `frontend/src/App.tsx`
- `frontend/src/main.tsx`
- `frontend/Dockerfile`

## Requirements

### Dependencies (package.json)
```json
{
  "dependencies": {
    "react": "^18",
    "react-dom": "^18"
  },
  "devDependencies": {
    "@types/react": "^18",
    "@vitejs/plugin-react": "^4",
    "typescript": "^5",
    "vite": "^5"
  }
}
```

### `api/types.ts`
Mirror all backend Pydantic schemas as TypeScript types:
```typescript
export interface Collection { id: string; name: string; description?: string; document_count: number; }
export interface Conversation { id: string; collection_id: string; title?: string; created_at: string; }
export interface Message { id: string; role: "user" | "assistant"; content: string; created_at: string; }
export interface Connector { name: string; source_type: string; last_synced_at?: string; }
```

### `api/client.ts`
Typed wrapper functions around `fetch`:
```typescript
export const api = {
  collections: { list, create, delete: del },
  conversations: { list, get, create, delete: del },
  chat: { stream },          // returns AsyncIterable<ChatEvent>
  connectors: { list, sync },
  documents: { upload },
}
```
`chat.stream()` should use the browser `EventSource` API (or `fetch` with `ReadableStream`) to consume the SSE endpoint.

### `App.tsx`
Shell layout: `<Sidebar />` on the left, `<ChatWindow />` on the right. No logic yet — just layout with placeholder components.

### `Dockerfile`
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```
`nginx.conf` must proxy `/api` to `http://backend:8000`.

## Acceptance criteria
- `npm run dev` starts the dev server on port 5173
- `docker compose up frontend` serves the built app on port 3000
- API client types match backend schemas' \
'["phase-5","frontend"]'

# ---------------------------------------------------------------------------

create_issue \
"[Phase 5] Sidebar component — conversation history and collection selector" \
'## Context
The left sidebar shows the list of past conversations (for navigation) and a way to create a new conversation (which starts with collection selection). This mirrors the OpenWebUI sidebar pattern.

## File to create
`frontend/src/components/Sidebar.tsx`

## Requirements

### Layout
```
┌─────────────────────┐
│  + New Conversation │  ← button
├─────────────────────┤
│  🟢 Recipes         │  ← active conversation (highlighted)
│  Yesterday          │
├─────────────────────┤
│  🟡 Gardening       │
│  3 days ago         │
├─────────────────────┤
│  ...                │
└─────────────────────┘
```

### Behaviour
- On mount: `api.conversations.list()` → render list with title + relative timestamp
- Click a conversation: emit `onConversationSelect(id)` to parent
- "New Conversation" button: open a modal/dropdown that:
  1. Calls `api.collections.list()`
  2. Shows collection names as clickable options
  3. On selection: calls `api.conversations.create({collection_id})`, then `onConversationSelect(newId)`
- Active conversation is highlighted
- Loading state: show skeleton placeholders
- Empty state: "No conversations yet — start one above"

### Props
```typescript
interface SidebarProps {
  activeConversationId: string | null;
  onConversationSelect: (id: string) => void;
}
```

## Dependencies
- `[Phase 5] Frontend scaffold` must be done first

## Acceptance criteria
- Sidebar renders conversation list fetched from the API
- Selecting a conversation updates the active highlight
- New conversation flow creates a conversation and switches to it' \
'["phase-5","frontend"]'

# ---------------------------------------------------------------------------

create_issue \
"[Phase 5] ChatWindow component with SSE streaming and DocumentUpload" \
'## Context
The main chat area renders the message thread for the active conversation and streams the assistant'\''s response token-by-token using Server-Sent Events. It also includes a file upload button for ingesting documents into the current collection.

## Files to create
- `frontend/src/components/ChatWindow.tsx`
- `frontend/src/components/DocumentUpload.tsx`

## Requirements

### `ChatWindow.tsx`
```typescript
interface ChatWindowProps {
  conversationId: string | null;
}
```

**Message thread:**
- On `conversationId` change: `api.conversations.get(id)` → render messages
- User messages right-aligned, assistant messages left-aligned
- Assistant messages render Markdown (use `react-markdown`)
- Auto-scroll to bottom on new messages

**Input bar:**
- Textarea (Shift+Enter = newline, Enter = send)
- Send button (disabled while streaming)
- On send:
  1. Optimistically append user message to thread
  2. Call `api.chat.stream({ conversation_id, message })`
  3. Append empty assistant message bubble, append tokens as they arrive
  4. On `done` event: message is complete
  5. On `error` event: show inline error, remove incomplete assistant bubble

**Loading state:** spinner while fetching conversation history
**Empty state:** "Select or start a conversation"

### `DocumentUpload.tsx`
- Paperclip icon button in the input bar area
- Opens a file picker (`accept=".pdf,.docx,.txt"`)
- On file select: calls `api.documents.upload(collection_id, file)`
- Shows upload progress (indeterminate spinner)
- On success: toast "Document uploaded and processing"
- On error: toast with error message
- `collection_id` is derived from the current conversation

## Dependencies
- `[Phase 5] Frontend scaffold` must be done first

## Extra dependencies
```
npm install react-markdown
```

## Acceptance criteria
- Tokens stream in real-time into the assistant bubble
- Markdown in assistant responses is rendered (bold, lists, code blocks)
- File upload triggers ingestion; document appears in collection after refresh' \
'["phase-5","frontend"]'

# ---------------------------------------------------------------------------
# PHASE 6 — E2E tests & polish
# ---------------------------------------------------------------------------

create_issue \
"[Phase 6] E2E tests — ingest, query, multi-turn, and '\''I don'\''t know'\'' path" \
'## Context
End-to-end tests validate the full system from HTTP request to response against a running Docker Compose stack. They are the highest-confidence tests and cover the critical happy paths described in the plan.

## File to create
`backend/tests/test_e2e.py`

## Test cases

### Setup (session-scoped fixture)
```python
@pytest.fixture(scope="session")
async def client():
    # httpx.AsyncClient pointed at http://localhost:8000
    # Requires full docker compose stack to be running
    ...
```

### Test 1: Ingest and query
```
1. POST /api/collections  {"name": "E2E Recipes"}
2. POST /api/collections/{id}/documents  (upload tests/fixtures/sample_recipe.txt)
3. Poll GET /api/collections/{id} until document_count == 1
4. POST /api/conversations  {"collection_id": id}
5. POST /api/chat  {"conversation_id": id, "message": "What ingredients does the recipe use?"}
6. Collect all SSE tokens into final answer
7. Assert answer contains at least one ingredient from the fixture file
```

### Test 2: Multi-turn follow-up
```
(continuing conversation from Test 1)
6. POST /api/chat  {"conversation_id": same_id, "message": "Can I substitute any of them?"}
7. Assert answer is coherent (not "I don'\''t know about that topic")
8. Assert answer does NOT re-list ingredients verbatim (demonstrates query rewriting)
```

### Test 3: "I don'\''t know" path
```
1. POST /api/collections  {"name": "E2E Gardening"}  (empty — no documents)
2. POST /api/conversations  {"collection_id": gardening_id}
3. POST /api/chat  {"conversation_id": id, "message": "What are the best pasta recipes?"}
4. Assert SSE response contains early_exit signal OR answer states no relevant context
```

### Test 4: Connector sync
```
1. POST /api/connectors/dummy/sync  (into a test collection)
2. Assert response {documents_ingested: 5}
3. Query "Tell me about risotto" against that collection
4. Assert answer mentions risotto
```

## Test fixture
`backend/tests/fixtures/sample_recipe.txt` — a short plain-text recipe with known ingredients (create this file as part of this issue).

## Marks
All tests: `@pytest.mark.e2e`
Run only with: `pytest -m e2e` (skipped in regular CI unless `RUN_E2E=true`)

## Acceptance criteria
- All 4 test cases pass against a running `docker compose up` stack
- Tests are skipped cleanly when the stack is not running' \
'["phase-6","testing","e2e"]'

# ---------------------------------------------------------------------------

create_issue \
"[Phase 6] Docker Compose polish, error handling, and environment documentation" \
'## Context
Final hardening pass to make the project production-presentable: proper healthchecks, graceful error handling across the stack, and complete environment variable documentation.

## Changes across the codebase

### Docker Compose (`docker-compose.yml`)
- Add `healthcheck` to backend service:
  ```yaml
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 10s
    timeout: 5s
    retries: 3
  ```
- Add `healthcheck` to ChromaDB service
- Set `depends_on` with `condition: service_healthy` for backend → postgres/chromadb
- Add `restart: unless-stopped` to all services (already in skeleton — verify)

### Backend error handling
- Add a global exception handler in `app/main.py`:
  ```python
  @app.exception_handler(Exception)
  async def global_handler(request, exc):
      # log the full traceback
      # return {"detail": "Internal server error"} with 500
  ```
- In the SSE chat endpoint: catch exceptions during streaming and emit `{"type": "error", "content": "..."}` before closing the stream (never leave the client hanging)
- In the ingestion pipeline: if parsing fails, set `Document.status = "failed"` and include `error_message`

### README updates
- Add a "Troubleshooting" section covering:
  - Ollama model not found → `ollama pull llama3`
  - ChromaDB connection error → check Docker network
  - Alembic "target database is not up to date" → `docker compose run backend alembic upgrade head`

### `.env.example` completeness
- Verify every env var consumed by `Settings` has a corresponding entry in `.env.example` with a comment

## Acceptance criteria
- `docker compose up` reaches healthy state for all services
- A 500 error in any domain returns JSON `{"detail": "..."}` not an HTML traceback
- SSE stream never hangs on error
- README troubleshooting covers the three most common setup failures' \
'["phase-6","devops","backend"]'

echo ""
echo "All issues created successfully!"
