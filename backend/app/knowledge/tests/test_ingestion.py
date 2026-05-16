import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.knowledge.chunker import chunk_document


# ── chunker unit tests ────────────────────────────────────────────────────────

@pytest.mark.unit
class TestChunkDocument:
    def test_returns_chunks(self):
        text = "word " * 500  # long enough to produce multiple chunks
        chunks = chunk_document(text, "doc1", "col1")
        assert len(chunks) > 0

    def test_chunk_carries_required_metadata(self):
        chunks = chunk_document("hello world " * 100, "doc-id", "col-id")
        for c in chunks:
            assert "child_text" in c
            assert "parent_id" in c
            assert "parent_text" in c
            assert c["doc_id"] == "doc-id"
            assert c["collection_id"] == "col-id"

    def test_parent_id_format(self):
        chunks = chunk_document("x " * 200, "mydoc", "mycol")
        assert all(c["parent_id"].startswith("mydoc_p") for c in chunks)

    def test_child_text_fits_inside_parent_text(self):
        chunks = chunk_document("hello " * 300, "d", "c")
        for c in chunks:
            assert c["child_text"] in c["parent_text"]

    def test_empty_text_returns_no_chunks(self):
        chunks = chunk_document("", "d", "c")
        assert chunks == []


# ── parse_file unit tests ─────────────────────────────────────────────────────

@pytest.mark.unit
class TestParseFile:
    def test_txt_file_returns_text(self):
        from app.knowledge.service import _parse_file

        content = b"Hello, world!"
        result = _parse_file(content, "sample.txt")
        assert "Hello" in result

    def test_unsupported_extension_raises(self):
        from app.knowledge.service import _parse_file

        with pytest.raises(ValueError, match="Unsupported"):
            _parse_file(b"data", "file.xyz")


# ── ingest_document unit tests ────────────────────────────────────────────────

@pytest.mark.unit
class TestIngestDocument:
    async def test_creates_document_row_and_returns_ready(self):
        from app.knowledge.service import ingest_document

        col_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.filename = "test.txt"
        mock_doc.status = "processing"

        db = AsyncMock()
        db.refresh = AsyncMock()

        mock_chroma_col = AsyncMock()
        mock_chroma = AsyncMock()
        mock_chroma.get_collection = AsyncMock(return_value=mock_chroma_col)

        with patch("app.knowledge.service.get_collection", AsyncMock(return_value=MagicMock())), \
             patch("app.knowledge.service.Document", return_value=mock_doc), \
             patch("app.knowledge.service._parse_file", return_value="some text " * 50), \
             patch("app.knowledge.service.chunk_document", return_value=[
                 {"child_text": "chunk", "parent_id": "p0", "parent_text": "parent", "doc_id": str(doc_id), "collection_id": str(col_id)}
             ]), \
             patch("app.knowledge.service.get_embeddings", return_value=MagicMock(embed_documents=MagicMock(return_value=[[0.1, 0.2]]))), \
             patch("app.knowledge.service.get_chroma_client", AsyncMock(return_value=mock_chroma)):

            result = await ingest_document(db, col_id, b"content", "test.txt")

        assert mock_doc.status == "ready"
        db.commit.assert_called()

    async def test_sets_status_failed_on_error(self):
        from app.knowledge.service import ingest_document

        mock_doc = MagicMock()
        mock_doc.id = uuid.uuid4()
        mock_doc.filename = "bad.txt"
        mock_doc.status = "processing"

        db = AsyncMock()
        db.refresh = AsyncMock()

        # _parse_file succeeds; error happens inside _ingest_text (during chunking)
        with patch("app.knowledge.service.get_collection", AsyncMock(return_value=MagicMock())), \
             patch("app.knowledge.service.Document", return_value=mock_doc), \
             patch("app.knowledge.service._parse_file", return_value="some text"), \
             patch("app.knowledge.service.chunk_document", side_effect=RuntimeError("chunk error")):

            with pytest.raises(RuntimeError):
                await ingest_document(db, uuid.uuid4(), b"x", "bad.txt")

        assert mock_doc.status == "failed"


# ── integration tests ─────────────────────────────────────────────────────────

@pytest.mark.integration
class TestIngestionIntegration:
    @pytest.fixture(autouse=True)
    def infrastructure(self, monkeypatch, tmp_path):
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
                monkeypatch.setenv("CHROMADB_HOST", chroma.get_container_host_ip())
                monkeypatch.setenv("CHROMADB_PORT", str(chroma.get_exposed_port(8000)))
                monkeypatch.setenv("EMBEDDING_PROVIDER", "ollama")

                get_settings.cache_clear()
                _get_engine.cache_clear()
                _get_session_factory.cache_clear()
                chromadb_module._client = None

                command.upgrade(Config("alembic.ini"), "head")

                self._tmp_path = tmp_path
                yield

                get_settings.cache_clear()
                _get_engine.cache_clear()
                _get_session_factory.cache_clear()
                chromadb_module._client = None

    async def test_ingest_txt_produces_chunks_in_chromadb(self):
        from app.knowledge.service import create_collection, ingest_document
        from app.knowledge.schemas import CollectionCreate
        from app.shared.database import _get_session_factory

        txt_content = b"The quick brown fox jumps over the lazy dog. " * 100

        mock_embeddings = MagicMock()
        mock_embeddings.embed_documents = MagicMock(
            side_effect=lambda texts: [[0.1] * 384 for _ in texts]
        )

        async with _get_session_factory()() as db:
            collection = await create_collection(db, CollectionCreate(name="TestCol"))

        with patch("app.knowledge.service.get_embeddings", return_value=mock_embeddings):
            async with _get_session_factory()() as db:
                result = await ingest_document(db, collection.id, txt_content, "test.txt")

        assert result.status == "ready"
        assert result.filename == "test.txt"

        from app.shared.chromadb import get_chroma_client
        chroma = await get_chroma_client()
        chroma_col = await chroma.get_collection(str(collection.id))
        count = await chroma_col.count()
        assert count > 0

    async def test_ingest_sets_failed_status_on_bad_file(self):
        from app.knowledge.service import create_collection, ingest_document
        from app.knowledge.schemas import CollectionCreate
        from app.shared.database import _get_session_factory

        async with _get_session_factory()() as db:
            collection = await create_collection(db, CollectionCreate(name="BadCol"))

        with pytest.raises(ValueError, match="Unsupported"):
            async with _get_session_factory()() as db:
                await ingest_document(db, collection.id, b"data", "file.xyz")
