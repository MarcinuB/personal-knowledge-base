# ADR 0001 — RAG Pipeline Strategy

## Status
Accepted

## Context

The system needs to retrieve relevant document context before generating answers.
The choice of chunking strategy and retrieval approach directly determines answer quality.
Several options exist, ranging from simple fixed-size chunking to complex multi-step pipelines.

## Decision

Use **parent-child (hierarchical) chunking** with a **cross-encoder reranker**, combined with
**history-aware query rewriting** for multi-turn conversations.

### Pipeline steps
1. **Query rewriting** — before any retrieval, rewrite the user's latest message into a
   self-contained question using LangChain's `create_history_aware_retriever`. Resolves
   dangling references in follow-up questions.
2. **Parent-child retrieval** — small child chunks (~200 tokens) are embedded and searched
   for precision. When a child chunk matches, its larger parent chunk (~800 tokens) is
   returned to the LLM for rich context. Implemented via `ParentDocumentRetriever`.
3. **Cross-encoder reranking** — after retrieving top-20 parent chunks, `cross-encoder/ms-marco-MiniLM`
   re-scores them by reading the query and each chunk together. Top-5 are passed to the LLM.
   Runs locally, no API cost.

## Alternatives Considered

| Approach | Rejected Because |
|---|---|
| Fixed-size chunking | Cuts mid-sentence; splits semantically related content |
| Semantic chunking only (no parent-child) | Retrieves precise chunks but LLM gets narrow context |
| RAG-Fusion (multi-query) | High complexity, high LLM cost; overkill for single-user personal KB |
| No reranker | Vector similarity alone has lower precision; one extra local model is worth it |
| Stuffing full chat history into prompt | Pollutes the embedding query; retrieval degrades in long conversations |

## Consequences

- Ingestion is slower (two-level chunking + embedding) but query quality is significantly higher
- The cross-encoder model (~85MB) is downloaded on first run; no GPU required
- Changing the chunking strategy later requires re-ingesting all documents
