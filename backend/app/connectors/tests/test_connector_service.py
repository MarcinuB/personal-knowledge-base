import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.documents import Document

from app.connectors.base import BaseConnector, ConnectorConfig


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_config(collection_id: uuid.UUID | None = None, name: str = "test") -> ConnectorConfig:
    return ConnectorConfig(
        name=name,
        source_type="dummy",
        collection_id=collection_id or uuid.uuid4(),
    )


class _FakeConnector(BaseConnector):
    def __init__(self, config: ConnectorConfig, docs: list[Document]) -> None:
        super().__init__(config)
        self._docs = docs

    async def sync(self) -> AsyncIterator[Document]:
        for doc in self._docs:
            yield doc

    async def health_check(self) -> bool:
        return True


# ── unit tests ────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestConnectorServiceRegistry:
    def _fresh_service(self):
        from app.connectors.service import ConnectorService
        return ConnectorService()

    def test_register_and_list(self):
        svc = self._fresh_service()
        connector = _FakeConnector(_make_config(name="a"), [])
        svc.register(connector)
        assert svc.list_connectors() == [connector]

    def test_duplicate_name_raises(self):
        svc = self._fresh_service()
        svc.register(_FakeConnector(_make_config(name="dup"), []))
        with pytest.raises(ValueError, match="already registered"):
            svc.register(_FakeConnector(_make_config(name="dup"), []))

    def test_get_unknown_raises(self):
        svc = self._fresh_service()
        with pytest.raises(KeyError):
            svc.get("nope")


@pytest.mark.unit
class TestConnectorServiceSync:
    def _fresh_service(self):
        from app.connectors.service import ConnectorService
        return ConnectorService()

    async def test_sync_calls_ingest_for_each_document(self):
        svc = self._fresh_service()
        col_id = uuid.uuid4()
        docs = [
            Document(page_content="Doc one", metadata={"source": "s1"}),
            Document(page_content="Doc two", metadata={"source": "s2"}),
        ]
        svc.register(_FakeConnector(_make_config(collection_id=col_id, name="fake"), docs))

        ingested_calls = []

        async def fake_ingest_text(db, collection_id, text, source_name, source_type):
            ingested_calls.append({"text": text, "source": source_name, "type": source_type})
            return MagicMock()

        db = AsyncMock()
        with patch("app.connectors.service._upsert_last_synced", AsyncMock()), \
             patch("app.knowledge.service._ingest_text", fake_ingest_text):
            count = await svc.sync("fake", db)

        assert count == 2
        assert ingested_calls[0] == {"text": "Doc one", "source": "s1", "type": "connector"}
        assert ingested_calls[1] == {"text": "Doc two", "source": "s2", "type": "connector"}

    async def test_sync_returns_zero_for_empty_connector(self):
        svc = self._fresh_service()
        svc.register(_FakeConnector(_make_config(name="empty"), []))

        db = AsyncMock()
        with patch("app.connectors.service._upsert_last_synced", AsyncMock()), \
             patch("app.knowledge.service._ingest_text", AsyncMock(return_value=MagicMock())):
            count = await svc.sync("empty", db)

        assert count == 0

    async def test_sync_unknown_connector_raises(self):
        svc = self._fresh_service()
        with pytest.raises(KeyError):
            await svc.sync("ghost", AsyncMock())

    async def test_source_type_is_connector(self):
        svc = self._fresh_service()
        svc.register(_FakeConnector(_make_config(name="chk"), [
            Document(page_content="hello", metadata={"source": "x"}),
        ]))

        captured = []

        async def capture(db, collection_id, text, source_name, source_type):
            captured.append(source_type)
            return MagicMock()

        with patch("app.connectors.service._upsert_last_synced", AsyncMock()), \
             patch("app.knowledge.service._ingest_text", capture):
            await svc.sync("chk", AsyncMock())

        assert captured == ["connector"]


@pytest.mark.unit
class TestDummyConnector:
    async def test_yields_default_document_when_no_settings(self):
        from app.connectors.dummy import DummyConnector
        connector = DummyConnector(_make_config())
        docs = [doc async for doc in connector.sync()]
        assert len(docs) == 1
        assert docs[0].page_content != ""

    async def test_yields_configured_documents(self):
        from app.connectors.dummy import DummyConnector
        config = ConnectorConfig(
            name="d",
            source_type="dummy",
            collection_id=uuid.uuid4(),
            settings={"documents": [
                {"content": "First", "source": "s1"},
                {"content": "Second", "source": "s2"},
            ]},
        )
        connector = DummyConnector(config)
        docs = [doc async for doc in connector.sync()]
        assert len(docs) == 2
        assert docs[0].page_content == "First"
        assert docs[1].page_content == "Second"

    async def test_health_check_returns_true(self):
        from app.connectors.dummy import DummyConnector
        connector = DummyConnector(_make_config())
        assert await connector.health_check() is True


# ── integration tests ─────────────────────────────────────────────────────────

@pytest.mark.integration
class TestConnectorServiceIntegration:
    @pytest.fixture(autouse=True)
    def infrastructure(self, monkeypatch):
        from alembic import command
        from alembic.config import Config
        from testcontainers.core.container import DockerContainer
        from testcontainers.postgres import PostgresContainer

        import app.shared.chromadb as chromadb_module
        from app.shared.config import get_settings
        from app.shared.database import _get_engine, _get_session_factory
        from conftest import wait_for_chroma

        with PostgresContainer("postgres:16-alpine") as pg:
            with DockerContainer("chromadb/chroma:latest").with_exposed_ports(8000) as chroma:
                chroma_host = chroma.get_container_host_ip()
                chroma_port = chroma.get_exposed_port(8000)
                wait_for_chroma(chroma_host, chroma_port)

                pg_url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+asyncpg://")
                monkeypatch.setenv("POSTGRES_URL", pg_url)
                monkeypatch.setenv("CHROMADB_HOST", chroma_host)
                monkeypatch.setenv("CHROMADB_PORT", str(chroma_port))

                get_settings.cache_clear()
                _get_engine.cache_clear()
                _get_session_factory.cache_clear()
                chromadb_module._client = None

                command.upgrade(Config("alembic.ini"), "head")

                yield

                get_settings.cache_clear()
                _get_engine.cache_clear()
                _get_session_factory.cache_clear()
                chromadb_module._client = None

    async def _create_collection(self, db):
        from app.knowledge.schemas import CollectionCreate
        from app.knowledge.service import create_collection
        return await create_collection(db, CollectionCreate(name=f"col-{uuid.uuid4().hex[:6]}"))

    async def test_sync_dummy_connector_ingests_documents(self):
        from app.connectors.dummy import DummyConnector
        from app.connectors.service import ConnectorService
        from app.shared.database import _get_session_factory

        mock_embeddings = MagicMock()
        mock_embeddings.embed_documents = MagicMock(
            side_effect=lambda texts: [[0.1] * 384 for _ in texts]
        )

        async with _get_session_factory()() as db:
            collection = await self._create_collection(db)

        svc = ConnectorService()
        svc.register(DummyConnector(ConnectorConfig(
            name="dummy",
            source_type="dummy",
            collection_id=collection.id,
            settings={"documents": [
                {"content": "Paris is the capital of France. " * 20, "source": "dummy://paris"},
                {"content": "Python is a programming language. " * 20, "source": "dummy://python"},
            ]},
        )))

        with patch("app.knowledge.service.get_embeddings", return_value=mock_embeddings):
            async with _get_session_factory()() as db:
                count = await svc.sync("dummy", db)

        assert count == 2

        from app.shared.chromadb import get_chroma_client
        chroma = await get_chroma_client()
        chroma_col = await chroma.get_collection(str(collection.id))
        assert await chroma_col.count() > 0

    async def test_last_synced_at_persisted_after_sync(self):
        from app.connectors.dummy import DummyConnector
        from app.connectors.service import ConnectorService
        from app.shared.database import _get_session_factory

        mock_embeddings = MagicMock()
        mock_embeddings.embed_documents = MagicMock(
            side_effect=lambda texts: [[0.1] * 384 for _ in texts]
        )

        async with _get_session_factory()() as db:
            collection = await self._create_collection(db)

        svc = ConnectorService()
        svc.register(DummyConnector(ConnectorConfig(
            name="timed",
            source_type="dummy",
            collection_id=collection.id,
        )))

        with patch("app.knowledge.service.get_embeddings", return_value=mock_embeddings):
            async with _get_session_factory()() as db:
                await svc.sync("timed", db)

        async with _get_session_factory()() as db:
            last_synced = await svc.get_last_synced_at(db, "timed")

        assert last_synced is not None

    async def test_list_connectors_endpoint(self):
        from app.connectors.dummy import DummyConnector
        from app.connectors.service import ConnectorService, connector_service
        from app.shared.database import _get_session_factory
        from httpx import ASGITransport, AsyncClient
        from app.main import app

        mock_embeddings = MagicMock()
        mock_embeddings.embed_documents = MagicMock(
            side_effect=lambda texts: [[0.1] * 384 for _ in texts]
        )

        async with _get_session_factory()() as db:
            collection = await self._create_collection(db)

        # Register on the module-level singleton
        name = f"integ-{uuid.uuid4().hex[:4]}"
        connector_service.register(DummyConnector(ConnectorConfig(
            name=name,
            source_type="dummy",
            collection_id=collection.id,
        )))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/connectors")

        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert name in names

        # cleanup singleton so other tests aren't affected
        del connector_service._registry[name]
