# ADR 0004 — Connector Interface Design

## Status
Accepted

## Context

The system needs to support multiple external data sources (Google Drive, Obsidian, etc.)
alongside manual file uploads. The connector system must be extensible without modifying
the core ingestion pipeline. The initial version only needs a DummyConnector.

## Decision

Define a `BaseConnector` abstract class with an `async def sync() -> AsyncIterator[Document]`
interface. Trigger connectors **manually** (user-initiated) for now, with the interface
designed to support scheduled sync later without changes.

```python
class BaseConnector(ABC):
    @abstractmethod
    async def sync(self) -> AsyncIterator[Document]: ...

    @abstractmethod
    async def health_check(self) -> bool: ...
```

The `ConnectorService` holds a registry of instantiated connectors and calls `sync()` when
the user triggers a manual sync. The resulting `Document` stream is handed directly to the
`knowledge/service.py` ingestion pipeline.

## Alternatives Considered

| Approach | Rejected Because |
|---|---|
| Synchronous `list[Document]` return | Blocks on large sources; async iterator is more scalable |
| Celery + Redis task queue from the start | Two extra Docker services for a feature not yet needed |
| Plugin-style dynamic loading | Overengineered; all connectors are in the same codebase |
| Pushing connector-specific logic into ingestion service | Breaks domain boundaries; connectors should own their fetch logic |

## Consequences

- Adding a new connector requires implementing two methods and registering it in `ConnectorService`
- Scheduled sync can be added later (APScheduler or Celery) without changing the connector interface
- `DummyConnector` provides a testable, zero-dependency example for the pattern
