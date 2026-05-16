import uuid
from datetime import datetime
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
