# ADR 0003 — Storage Architecture (PostgreSQL + ChromaDB)

## Status
Accepted

## Context

The system has two distinct storage needs:
1. Document vectors + chunks for semantic search
2. Relational data: collections, conversations, messages, connector sync state

These could be served by a single database or by purpose-built stores.

## Decision

Use **two separate databases**:
- **ChromaDB** for all vector and chunk storage
- **PostgreSQL** for all relational/metadata storage

## Rationale

ChromaDB is purpose-built for approximate nearest-neighbor (ANN) search with metadata
filtering. Using PostgreSQL with `pgvector` would work but requires more operational
knowledge (index tuning, HNSW vs IVFFlat) and is harder to run locally without GPU.
ChromaDB runs as a lightweight Docker container with zero configuration.

PostgreSQL is the right choice for relational data: conversations have foreign keys to
collections, messages belong to conversations, connectors have sync history. A document
store (MongoDB) would lose these relationships.

## Alternatives Considered

| Approach | Rejected Because |
|---|---|
| PostgreSQL + pgvector only | More complex vector tuning; `pgvector` less beginner-friendly than ChromaDB |
| ChromaDB only (store chat in metadata) | No relational queries; no foreign keys; awkward for message history |
| SQLite instead of PostgreSQL | Not suitable for Docker multi-container setups; concurrency issues |
| MongoDB for relational data | Loses referential integrity; no clear benefit over PostgreSQL here |

## Consequences

- Two Docker services instead of one for persistence
- ChromaDB and PostgreSQL must stay in sync (a document deleted from Postgres should be deleted from ChromaDB too — handled in `knowledge/service.py`)
- Backup requires two separate backup strategies
