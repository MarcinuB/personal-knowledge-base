import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.chat.schemas import ConversationCreate


# ── unit tests ────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestCreateConversation:
    async def test_returns_conversation_read(self):
        from app.chat.service import create_conversation

        col_id = uuid.uuid4()
        conv_id = uuid.uuid4()

        mock_conv = MagicMock()
        mock_conv.id = conv_id
        mock_conv.collection_id = col_id
        mock_conv.title = None
        mock_conv.created_at = MagicMock()

        db = AsyncMock()
        db.refresh = AsyncMock()

        from unittest.mock import patch
        with patch("app.chat.service.Conversation", return_value=mock_conv):
            result = await create_conversation(db, ConversationCreate(collection_id=col_id))

        db.add.assert_called_once()
        db.commit.assert_called_once()
        assert result.id == conv_id
        assert result.messages == []


@pytest.mark.unit
class TestGetConversation:
    async def test_raises_404_when_not_found(self):
        from app.chat.service import get_conversation

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        with pytest.raises(HTTPException) as exc_info:
            await get_conversation(db, uuid.uuid4())

        assert exc_info.value.status_code == 404


@pytest.mark.unit
class TestDeleteConversation:
    async def test_raises_404_when_not_found(self):
        from app.chat.service import delete_conversation

        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        with pytest.raises(HTTPException) as exc_info:
            await delete_conversation(db, uuid.uuid4())

        assert exc_info.value.status_code == 404

    async def test_deletes_conversation(self):
        from app.chat.service import delete_conversation

        mock_conv = MagicMock()
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_conv)))

        await delete_conversation(db, uuid.uuid4())

        db.delete.assert_called_once_with(mock_conv)
        db.commit.assert_called_once()


# ── integration tests ─────────────────────────────────────────────────────────

@pytest.mark.integration
class TestConversationServiceIntegration:
    @pytest.fixture(autouse=True)
    def infrastructure(self, monkeypatch):
        from alembic import command
        from alembic.config import Config
        from testcontainers.postgres import PostgresContainer

        from app.shared.config import get_settings
        from app.shared.database import _get_engine, _get_session_factory

        with PostgresContainer("postgres:16-alpine") as pg:
            pg_url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+asyncpg://")
            monkeypatch.setenv("POSTGRES_URL", pg_url)

            get_settings.cache_clear()
            _get_engine.cache_clear()
            _get_session_factory.cache_clear()

            command.upgrade(Config("alembic.ini"), "head")

            yield

            get_settings.cache_clear()
            _get_engine.cache_clear()
            _get_session_factory.cache_clear()

    async def _create_collection(self, db):
        from app.knowledge.service import create_collection
        from app.knowledge.schemas import CollectionCreate
        from unittest.mock import patch, AsyncMock
        mock_chroma = AsyncMock()
        with patch("app.knowledge.service.get_chroma_client", AsyncMock(return_value=mock_chroma)):
            return await create_collection(db, CollectionCreate(name=f"col-{uuid.uuid4().hex[:6]}"))

    async def test_create_and_get_conversation(self):
        from app.chat.service import create_conversation, get_conversation
        from app.shared.database import _get_session_factory

        async with _get_session_factory()() as db:
            collection = await self._create_collection(db)

        async with _get_session_factory()() as db:
            created = await create_conversation(db, ConversationCreate(collection_id=collection.id))

        async with _get_session_factory()() as db:
            fetched = await get_conversation(db, created.id)

        assert fetched.id == created.id
        assert fetched.collection_id == collection.id
        assert fetched.messages == []

    async def test_list_returns_reverse_chronological_order(self):
        from app.chat.service import create_conversation, list_conversations
        from app.shared.database import _get_session_factory
        import asyncio

        async with _get_session_factory()() as db:
            collection = await self._create_collection(db)

        async with _get_session_factory()() as db:
            first = await create_conversation(db, ConversationCreate(collection_id=collection.id, title="First"))
        await asyncio.sleep(0.01)
        async with _get_session_factory()() as db:
            second = await create_conversation(db, ConversationCreate(collection_id=collection.id, title="Second"))

        async with _get_session_factory()() as db:
            conversations = await list_conversations(db)

        assert conversations[0].id == second.id
        assert conversations[1].id == first.id

    async def test_delete_removes_conversation_and_messages(self):
        from app.chat.service import create_conversation, delete_conversation, get_conversation, add_message
        from app.shared.database import _get_session_factory

        async with _get_session_factory()() as db:
            collection = await self._create_collection(db)

        async with _get_session_factory()() as db:
            conv = await create_conversation(db, ConversationCreate(collection_id=collection.id))

        async with _get_session_factory()() as db:
            await add_message(db, conv.id, "user", "Hello")

        async with _get_session_factory()() as db:
            await delete_conversation(db, conv.id)

        async with _get_session_factory()() as db:
            with pytest.raises(HTTPException) as exc_info:
                await get_conversation(db, conv.id)
        assert exc_info.value.status_code == 404

    async def test_add_message_sets_title_from_first_user_message(self):
        from app.chat.service import create_conversation, add_message, get_conversation
        from app.shared.database import _get_session_factory

        async with _get_session_factory()() as db:
            collection = await self._create_collection(db)

        async with _get_session_factory()() as db:
            conv = await create_conversation(db, ConversationCreate(collection_id=collection.id))

        assert conv.title is None

        async with _get_session_factory()() as db:
            await add_message(db, conv.id, "user", "What is the capital of France?")

        async with _get_session_factory()() as db:
            fetched = await get_conversation(db, conv.id)

        assert fetched.title == "What is the capital of France?"

    async def test_messages_ordered_by_created_at(self):
        from app.chat.service import create_conversation, add_message, get_conversation
        from app.shared.database import _get_session_factory
        import asyncio

        async with _get_session_factory()() as db:
            collection = await self._create_collection(db)

        async with _get_session_factory()() as db:
            conv = await create_conversation(db, ConversationCreate(collection_id=collection.id))

        async with _get_session_factory()() as db:
            await add_message(db, conv.id, "user", "First")
        await asyncio.sleep(0.01)
        async with _get_session_factory()() as db:
            await add_message(db, conv.id, "assistant", "Second")

        async with _get_session_factory()() as db:
            fetched = await get_conversation(db, conv.id)

        assert fetched.messages[0].role == "user"
        assert fetched.messages[1].role == "assistant"
