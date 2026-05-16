from collections.abc import AsyncIterator

from langchain_core.documents import Document

from app.connectors.base import BaseConnector, ConnectorConfig


_DEFAULT_DOCUMENTS = [
    {"content": "Carbonara is a Roman pasta dish made with eggs, Pecorino Romano, guanciale, and black pepper.", "source": "dummy://carbonara", "category": "cooking"},
    {"content": "Tomatoes thrive in full sun and need consistent watering to prevent blossom-end rot.", "source": "dummy://tomatoes", "category": "gardening"},
    {"content": "Sourdough starter is a live culture of wild yeast and bacteria fed with flour and water.", "source": "dummy://sourdough", "category": "cooking"},
    {"content": "Basil grows best in warm temperatures above 10°C and should be pinched to prevent flowering.", "source": "dummy://basil", "category": "gardening"},
    {"content": "Risotto requires constant stirring and gradual stock addition to release starch from Arborio rice.", "source": "dummy://risotto", "category": "cooking"},
]


class DummyConnector(BaseConnector):
    """A connector that yields a fixed set of in-memory documents.

    Useful for smoke-testing the full connector pipeline without any
    external dependencies. The documents to yield are passed via
    ``config.settings["documents"]`` — a list of dicts with keys
    ``content``, optionally ``source``, and optionally ``category``.
    Falls back to five hardcoded cooking/gardening documents when
    ``settings`` is empty.
    """

    async def sync(self) -> AsyncIterator[Document]:
        docs = self.config.settings.get("documents") or _DEFAULT_DOCUMENTS
        for doc in docs:
            metadata: dict = {"source": doc.get("source", "dummy://unknown")}
            if "category" in doc:
                metadata["category"] = doc["category"]
            yield Document(page_content=doc["content"], metadata=metadata)

    async def health_check(self) -> bool:
        return True
