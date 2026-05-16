import uuid

import pytest

from app.connectors.base import ConnectorConfig
from app.connectors.dummy import DummyConnector, _DEFAULT_DOCUMENTS


def _make_config(**kwargs) -> ConnectorConfig:
    return ConnectorConfig(
        name=kwargs.get("name", "dummy"),
        source_type="dummy",
        collection_id=kwargs.get("collection_id", uuid.uuid4()),
        settings=kwargs.get("settings", {}),
    )


@pytest.mark.unit
class TestDummyConnector:
    async def test_sync_yields_five_documents_by_default(self):
        connector = DummyConnector(_make_config())
        docs = [doc async for doc in connector.sync()]
        assert len(docs) == 5

    async def test_all_default_documents_have_dummy_source(self):
        connector = DummyConnector(_make_config())
        docs = [doc async for doc in connector.sync()]
        assert all(doc.metadata["source"].startswith("dummy://") for doc in docs)

    async def test_all_default_documents_have_category(self):
        connector = DummyConnector(_make_config())
        docs = [doc async for doc in connector.sync()]
        assert all("category" in doc.metadata for doc in docs)

    async def test_default_documents_cover_cooking_and_gardening(self):
        connector = DummyConnector(_make_config())
        docs = [doc async for doc in connector.sync()]
        categories = {doc.metadata["category"] for doc in docs}
        assert "cooking" in categories
        assert "gardening" in categories

    async def test_health_check_returns_true(self):
        connector = DummyConnector(_make_config())
        assert await connector.health_check() is True

    async def test_settings_documents_override_defaults(self):
        config = _make_config(settings={"documents": [
            {"content": "First", "source": "dummy://first"},
            {"content": "Second", "source": "dummy://second"},
        ]})
        connector = DummyConnector(config)
        docs = [doc async for doc in connector.sync()]
        assert len(docs) == 2
        assert docs[0].page_content == "First"
        assert docs[1].page_content == "Second"
