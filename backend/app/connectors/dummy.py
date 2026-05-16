from collections.abc import AsyncIterator

from langchain_core.documents import Document

from app.connectors.base import BaseConnector, ConnectorConfig


class DummyConnector(BaseConnector):
    """A connector that yields a fixed set of in-memory documents.

    Useful for smoke-testing the full connector pipeline without any
    external dependencies. The documents to yield are passed via
    ``config.settings["documents"]`` — a list of dicts with keys
    ``content`` and optionally ``source``.  Falls back to a single
    default document when ``settings`` is empty.
    """

    async def sync(self) -> AsyncIterator[Document]:
        docs = self.config.settings.get("documents") or [
            {"content": "This is a dummy document for testing purposes.", "source": "dummy://default"},
        ]
        for doc in docs:
            yield Document(
                page_content=doc["content"],
                metadata={"source": doc.get("source", "dummy://unknown")},
            )

    async def health_check(self) -> bool:
        return True
