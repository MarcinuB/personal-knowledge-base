import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.knowledge.schemas import CollectionCreate


def _make_collection(**kwargs):
    defaults = dict(
        id=uuid.uuid4(),
        name="Test",
        description=None,
        created_at=datetime.utcnow(),
    )
    col = MagicMock(**{**defaults, **kwargs})
    col.id = defaults["id"]
    col.name = defaults["name"]
    col.description = defaults["description"]
    col.created_at = defaults["created_at"]
    return col


@pytest.mark.unit
class TestCreateCollection:
    async def test_creates_postgres_row_and_chroma_collection(self):
        from app.knowledge.service import create_collection

        col = _make_collection(name="Recipes")
        db = AsyncMock()
        db.refresh = AsyncMock(side_effect=lambda obj: None)

        mock_chroma = AsyncMock()
        with patch("app.knowledge.service.get_chroma_client", return_value=AsyncMock(return_value=mock_chroma)):
            with patch("app.knowledge.service.Collection", return_value=col):
                result = await create_collection(db, CollectionCreate(name="Recipes"))

        db.add.assert_called_once()
        db.commit.assert_called_once()

    async def test_returns_collection_read(self):
        from app.knowledge.service import create_collection

        col = _make_collection(name="Recipes")
        db = AsyncMock()
        db.refresh = AsyncMock()

        mock_chroma = AsyncMock()
        with patch("app.knowledge.service.get_chroma_client", AsyncMock(return_value=mock_chroma)):
            with patch("app.knowledge.service.Collection", return_value=col):
                result = await create_collection(db, CollectionCreate(name="Recipes"))

        assert result.name == col.name
        assert result.document_count == 0


@pytest.mark.unit
class TestDeleteCollection:
    async def test_raises_404_when_not_found(self):
        from app.knowledge.service import delete_collection

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        with pytest.raises(HTTPException) as exc_info:
            await delete_collection(db, uuid.uuid4())

        assert exc_info.value.status_code == 404

    async def test_deletes_from_postgres_and_chroma(self):
        from app.knowledge.service import delete_collection

        col = _make_collection()
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=col)))

        mock_chroma = AsyncMock()
        with patch("app.knowledge.service.get_chroma_client", AsyncMock(return_value=mock_chroma)):
            await delete_collection(db, col.id)

        db.delete.assert_called_once_with(col)
        db.commit.assert_called_once()
        mock_chroma.delete_collection.assert_called_once_with(str(col.id))


@pytest.mark.unit
class TestGetCollection:
    async def test_raises_404_when_not_found(self):
        from app.knowledge.service import get_collection

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(first=MagicMock(return_value=None)))

        with pytest.raises(HTTPException) as exc_info:
            await get_collection(db, uuid.uuid4())

        assert exc_info.value.status_code == 404


@pytest.mark.integration
class TestCollectionServiceIntegration:
    @pytest.fixture(autouse=True)
    def infrastructure(self, monkeypatch):
        from alembic import command
        from alembic.config import Config
        from testcontainers.core.container import DockerContainer
        from testcontainers.core.waiting_utils import wait_for_logs
        from testcontainers.postgres import PostgresContainer

        import app.shared.chromadb as chromadb_module
        from app.shared.config import get_settings
        from app.shared.database import _get_engine, _get_session_factory

        with PostgresContainer("postgres:16-alpine") as pg:
            with DockerContainer("chromadb/chroma:latest").with_exposed_ports(8000) as chroma:
                wait_for_logs(chroma, "Application startup complete", timeout=30)

                pg_url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+asyncpg://")
                chroma_host = chroma.get_container_host_ip()
                chroma_port = chroma.get_exposed_port(8000)

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

    async def test_create_persists_to_postgres_and_chromadb(self):
        from app.knowledge.service import create_collection, list_collections
        from app.shared.database import _get_session_factory

        async with _get_session_factory()() as db:
            result = await create_collection(db, CollectionCreate(name="Recipes", description="My recipes"))

        assert result.name == "Recipes"
        assert result.description == "My recipes"
        assert result.document_count == 0

        async with _get_session_factory()() as db:
            collections = await list_collections(db)

        assert len(collections) == 1
        assert collections[0].name == "Recipes"

    async def test_get_collection_returns_correct_data(self):
        from app.knowledge.service import create_collection, get_collection
        from app.shared.database import _get_session_factory

        async with _get_session_factory()() as db:
            created = await create_collection(db, CollectionCreate(name="Gardening", description="Plants"))

        async with _get_session_factory()() as db:
            fetched = await get_collection(db, created.id)

        assert fetched.id == created.id
        assert fetched.name == "Gardening"
        assert fetched.description == "Plants"

    async def test_delete_removes_from_postgres_and_chromadb(self):
        from app.knowledge.service import create_collection, delete_collection, list_collections
        from app.shared.database import _get_session_factory

        async with _get_session_factory()() as db:
            created = await create_collection(db, CollectionCreate(name="ToDelete"))

        async with _get_session_factory()() as db:
            await delete_collection(db, created.id)

        async with _get_session_factory()() as db:
            collections = await list_collections(db)

        assert len(collections) == 0

    async def test_delete_nonexistent_raises_404(self):
        from app.knowledge.service import delete_collection
        from app.shared.database import _get_session_factory

        async with _get_session_factory()() as db:
            with pytest.raises(HTTPException) as exc_info:
                await delete_collection(db, uuid.uuid4())

        assert exc_info.value.status_code == 404

    async def test_list_returns_document_count(self):
        from app.knowledge.service import create_collection, list_collections
        from app.shared.database import _get_session_factory

        async with _get_session_factory()() as db:
            await create_collection(db, CollectionCreate(name="First"))
        async with _get_session_factory()() as db:
            await create_collection(db, CollectionCreate(name="Second"))

        async with _get_session_factory()() as db:
            collections = await list_collections(db)

        assert len(collections) == 2
        assert all(c.document_count == 0 for c in collections)
