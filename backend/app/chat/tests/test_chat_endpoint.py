import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# ── unit tests ────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestChatEndpointUnit:
    async def test_returns_404_for_unknown_conversation(self):
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            with patch("app.chat.service.get_conversation", AsyncMock(side_effect=__import__("fastapi").HTTPException(status_code=404, detail="Conversation not found"))):
                resp = await client.post("/api/chat", json={"conversation_id": str(uuid.uuid4()), "message": "hi"})

        assert resp.status_code == 404

    async def test_streams_token_and_done_events(self):
        from app.main import app

        conv_id = uuid.uuid4()
        col_id = uuid.uuid4()
        msg_id = uuid.uuid4()

        mock_conv = MagicMock()
        mock_conv.collection_id = col_id
        mock_conv.messages = []

        mock_assistant_msg = MagicMock()
        mock_assistant_msg.id = msg_id

        async def fake_pipeline(**kwargs):
            for token in ["Hello", " world"]:
                yield token

        with patch("app.chat.service.get_conversation", AsyncMock(return_value=mock_conv)), \
             patch("app.chat.service.add_message", AsyncMock(return_value=mock_assistant_msg)), \
             patch("app.chat.router._get_session_factory") as mock_sf, \
             patch("app.chat.router.run_rag_pipeline", new=fake_pipeline):

            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_sf.return_value.return_value = mock_session

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                async with client.stream("POST", "/api/chat", json={"conversation_id": str(conv_id), "message": "hi"}) as resp:
                    assert resp.status_code == 200
                    assert "text/event-stream" in resp.headers["content-type"]
                    events = []
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            events.append(json.loads(line[6:]))

        token_events = [e for e in events if e["type"] == "token"]
        done_events = [e for e in events if e["type"] == "done"]

        assert len(token_events) == 2
        assert token_events[0]["content"] == "Hello"
        assert token_events[1]["content"] == " world"
        assert len(done_events) == 1
        assert done_events[0]["conversation_id"] == str(conv_id)
        assert done_events[0]["message_id"] == str(msg_id)

    async def test_streams_error_event_on_pipeline_failure(self):
        from app.main import app

        conv_id = uuid.uuid4()
        col_id = uuid.uuid4()

        mock_conv = MagicMock()
        mock_conv.collection_id = col_id
        mock_conv.messages = []

        async def failing_pipeline(**kwargs):
            raise RuntimeError("pipeline exploded")
            yield  # make it a generator

        with patch("app.chat.service.get_conversation", AsyncMock(return_value=mock_conv)), \
             patch("app.chat.service.add_message", AsyncMock(return_value=MagicMock())), \
             patch("app.chat.router._get_session_factory") as mock_sf, \
             patch("app.chat.router.run_rag_pipeline", new=failing_pipeline):

            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_sf.return_value.return_value = mock_session

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                async with client.stream("POST", "/api/chat", json={"conversation_id": str(conv_id), "message": "hi"}) as resp:
                    assert resp.status_code == 200
                    events = []
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            events.append(json.loads(line[6:]))

        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "pipeline exploded" in error_events[0]["content"]

    async def test_message_history_passed_to_pipeline(self):
        from app.main import app

        conv_id = uuid.uuid4()
        col_id = uuid.uuid4()

        user_msg = MagicMock()
        user_msg.role = "user"
        user_msg.content = "What is Python?"

        assistant_msg = MagicMock()
        assistant_msg.role = "assistant"
        assistant_msg.content = "A programming language."

        mock_conv = MagicMock()
        mock_conv.collection_id = col_id
        mock_conv.messages = [user_msg, assistant_msg]

        captured_messages = []

        async def capture_pipeline(collection_id, conversation_id, user_message, messages):
            captured_messages.extend(messages)
            yield "ok"

        with patch("app.chat.service.get_conversation", AsyncMock(return_value=mock_conv)), \
             patch("app.chat.service.add_message", AsyncMock(return_value=MagicMock())), \
             patch("app.chat.router._get_session_factory") as mock_sf, \
             patch("app.chat.router.run_rag_pipeline", new=capture_pipeline):

            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_sf.return_value.return_value = mock_session

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                async with client.stream("POST", "/api/chat", json={"conversation_id": str(conv_id), "message": "Tell me more"}) as resp:
                    async for _ in resp.aiter_lines():
                        pass

        assert captured_messages == [
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "A programming language."},
        ]

    async def test_user_message_persisted_before_streaming(self):
        from app.main import app

        conv_id = uuid.uuid4()
        col_id = uuid.uuid4()

        mock_conv = MagicMock()
        mock_conv.collection_id = col_id
        mock_conv.messages = []

        call_order = []

        async def fake_pipeline(**kwargs):
            call_order.append("pipeline")
            yield "answer"

        async def fake_add_message(db, conversation_id, role, content):
            call_order.append(f"add_message:{role}")
            return MagicMock(id=uuid.uuid4())

        with patch("app.chat.service.get_conversation", AsyncMock(return_value=mock_conv)), \
             patch("app.chat.service.add_message", fake_add_message), \
             patch("app.chat.router._get_session_factory") as mock_sf, \
             patch("app.chat.router.run_rag_pipeline", new=fake_pipeline):

            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_sf.return_value.return_value = mock_session

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                async with client.stream("POST", "/api/chat", json={"conversation_id": str(conv_id), "message": "hi"}) as resp:
                    async for _ in resp.aiter_lines():
                        pass

        assert call_order.index("add_message:user") < call_order.index("pipeline")
        assert call_order.index("pipeline") < call_order.index("add_message:assistant")


# ── integration tests ─────────────────────────────────────────────────────────

@pytest.mark.integration
class TestChatEndpointIntegration:
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

    async def _setup_conversation(self):
        from app.knowledge.schemas import CollectionCreate
        from app.knowledge.service import create_collection
        from app.chat.schemas import ConversationCreate
        from app.chat.service import create_conversation
        from app.shared.database import _get_session_factory
        from app.shared.chromadb import get_chroma_client

        async with _get_session_factory()() as db:
            with patch("app.knowledge.service.get_chroma_client", AsyncMock(return_value=AsyncMock())):
                collection = await create_collection(db, CollectionCreate(name="test-col"))

        async with _get_session_factory()() as db:
            conversation = await create_conversation(db, ConversationCreate(collection_id=collection.id))

        # Create an empty ChromaDB collection so collection_router passes
        client = await get_chroma_client()
        chroma_col = await client.create_collection(str(collection.id))
        await chroma_col.add(
            ids=[str(uuid.uuid4())],
            embeddings=[[0.1] * 384],
            documents=["Paris is the capital of France."],
            metadatas=[{"parent_id": "p0", "parent_text": "Paris is the capital of France.", "doc_id": "d1", "collection_id": str(collection.id)}],
        )

        return conversation

    async def test_post_chat_streams_token_and_done_events(self):
        from app.main import app

        conversation = await self._setup_conversation()

        mock_embeddings = MagicMock()
        mock_embeddings.embed_query = MagicMock(return_value=[0.1] * 384)

        async def fake_astream(messages):
            from langchain_core.messages import AIMessageChunk
            for word in ["Paris", " is", " the", " answer."]:
                yield AIMessageChunk(content=word)

        mock_llm = MagicMock()
        mock_llm.astream = fake_astream

        events = []
        with patch("app.chat.graph.get_embeddings", return_value=mock_embeddings), \
             patch("app.chat.graph.get_settings", return_value=MagicMock()), \
             patch("app.chat.graph.get_llm", return_value=mock_llm), \
             patch("app.chat.graph.rerank", return_value=["Paris is the capital of France."]):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                async with client.stream("POST", "/api/chat", json={"conversation_id": str(conversation.id), "message": "What is the capital?"}) as resp:
                    assert resp.status_code == 200
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            events.append(json.loads(line[6:]))

        token_events = [e for e in events if e["type"] == "token"]
        done_events = [e for e in events if e["type"] == "done"]

        assert len(token_events) > 0
        assert len(done_events) == 1
        assert done_events[0]["conversation_id"] == str(conversation.id)
        assert "message_id" in done_events[0]

    async def test_messages_persisted_to_db_after_stream(self):
        from app.main import app
        from app.chat.service import get_conversation
        from app.shared.database import _get_session_factory

        conversation = await self._setup_conversation()

        mock_embeddings = MagicMock()
        mock_embeddings.embed_query = MagicMock(return_value=[0.1] * 384)

        async def fake_astream(messages):
            from langchain_core.messages import AIMessageChunk
            yield AIMessageChunk(content="The capital is Paris.")

        mock_llm = MagicMock()
        mock_llm.astream = fake_astream

        with patch("app.chat.graph.get_embeddings", return_value=mock_embeddings), \
             patch("app.chat.graph.get_settings", return_value=MagicMock()), \
             patch("app.chat.graph.get_llm", return_value=mock_llm), \
             patch("app.chat.graph.rerank", return_value=["Paris is the capital of France."]):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                async with client.stream("POST", "/api/chat", json={"conversation_id": str(conversation.id), "message": "What is the capital?"}) as resp:
                    async for _ in resp.aiter_lines():
                        pass

        async with _get_session_factory()() as db:
            fetched = await get_conversation(db, conversation.id)

        assert len(fetched.messages) == 2
        assert fetched.messages[0].role == "user"
        assert fetched.messages[0].content == "What is the capital?"
        assert fetched.messages[1].role == "assistant"
        assert "Paris" in fetched.messages[1].content
