# ADR 0002 — DDD Bounded Context Code Structure

## Status
Accepted

## Context

The backend codebase needs an organizing principle. Two common approaches exist:
technical layering (split by what code does) and domain-driven design (split by
business capability). The choice affects navigability, testability, and how naturally
the code scales.

## Decision

Organize the backend using **DDD-style bounded contexts**:

```
backend/app/
├── knowledge/   # Collections + document ingestion
├── chat/        # Conversations + RAG pipeline
├── connectors/  # External data source adapters
└── shared/      # Cross-cutting infrastructure
```

Each domain owns its models, schemas, service layer, API routes, and tests.
Domains are only allowed to depend on `shared/`; they do not import from each other directly.

## Alternatives Considered

| Approach | Rejected Because |
|---|---|
| Technical layers (`models/`, `services/`, `routers/`) | All knowledge-related files scattered across 4+ folders; hard to navigate; doesn't signal business intent |
| Single flat module | No separation of concerns; grows unmanageable quickly |
| Microservices (separate processes per domain) | Massively overengineered for a single-user portfolio project |

## Consequences

- Each domain is independently testable with its own test suite
- Adding a new domain (e.g. `users/`) is a contained change
- Cross-domain queries (e.g. "list collections in a conversation") require explicit service calls, not ORM joins — a deliberate constraint
- Slight verbosity: each domain has the same file structure, which feels repetitive for small domains like `connectors/`
