# Domain Glossary

This file defines the ubiquitous language for the Personal Knowledge Base system.
All code, documentation, and conversations should use these terms consistently.

---

## Core Terms

### Collection
A named, isolated set of documents belonging to a single topic (e.g. "Recipes", "Gardening").
Each Collection maps to a dedicated ChromaDB collection and is the unit of knowledge organization.
A user creates Collections and uploads documents into them. A user selects a Collection at the start of each Conversation.

### Document
A single uploaded file (PDF, DOCX, TXT) or a piece of content synced from a Connector.
A Document belongs to exactly one Collection. It is the raw input to the ingestion pipeline.

### Chunk
A fragment of a Document stored in ChromaDB for vector search. The system uses a parent-child chunking strategy:
- **Child Chunk**: a small, precisely-sized text fragment stored with an embedding. Used for semantic search.
- **Parent Chunk**: the larger surrounding passage returned to the LLM as context when a child chunk matches.

### Embedding
A numerical vector representation of a Chunk, computed by the embedding model (`nomic-embed-text` via Ollama by default).
Embeddings are stored in ChromaDB alongside their parent Chunk IDs.

### Connector
An adapter that pulls Documents from an external source (Google Drive, Obsidian, etc.) into a Collection.
Every Connector implements the `BaseConnector` interface and is triggered manually by the user.

### Conversation
A single chat session between a user and the system, scoped to one Collection.
A Conversation has a sequence of Messages and is persisted in PostgreSQL.

### Message
A single turn within a Conversation. Has a role (`user` or `assistant`) and content (text).
Messages are used both for display in the UI and as history context for the RAG pipeline.

### Query Rewriting
The process of transforming a user's follow-up Message into a self-contained question using prior Message history.
Performed before every vector search to resolve dangling references ("that ingredient", "the second one", etc.).

### Retrieval Pipeline
The sequence of steps that turns a user query into an LLM-generated answer:
1. Query Rewriting
2. Vector Search (child chunks via ChromaDB)
3. Parent Chunk Expansion
4. Reranking (cross-encoder)
5. LLM Generation

### Reranker
A cross-encoder model (`cross-encoder/ms-marco-MiniLM`) that re-scores retrieved Parent Chunks for relevance
after vector search. Runs locally, no external API required.
