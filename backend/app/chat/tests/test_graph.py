import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── reranker unit tests ───────────────────────────────────────────────────────

@pytest.mark.unit
class TestRerank:
    def test_returns_top_k_in_score_order(self):
        from app.chat.reranker import rerank

        chunks = ["apple", "banana", "cherry"]
        mock_encoder = MagicMock()
        mock_encoder.predict.return_value = [0.1, 0.9, 0.5]

        with patch("app.chat.reranker._get_cross_encoder", return_value=mock_encoder):
            result = rerank("query", chunks, top_k=2)

        assert result == ["banana", "cherry"]

    def test_empty_chunks_returns_empty(self):
        from app.chat.reranker import rerank

        result = rerank("query", [], top_k=5)
        assert result == []

    def test_top_k_caps_results(self):
        from app.chat.reranker import rerank

        chunks = ["a", "b", "c", "d", "e"]
        mock_encoder = MagicMock()
        mock_encoder.predict.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]

        with patch("app.chat.reranker._get_cross_encoder", return_value=mock_encoder):
            result = rerank("query", chunks, top_k=3)

        assert len(result) == 3


# ── graph node unit tests ─────────────────────────────────────────────────────

@pytest.mark.unit
class TestCollectionRouter:
    async def test_early_exit_when_collection_empty(self):
        from app.chat.graph import collection_router

        mock_collection = AsyncMock()
        mock_collection.count = AsyncMock(return_value=0)
        mock_client = AsyncMock()
        mock_client.get_collection = AsyncMock(return_value=mock_collection)

        with patch("app.chat.graph.get_chroma_client", AsyncMock(return_value=mock_client)):
            result = await collection_router({
                "collection_id": str(uuid.uuid4()),
                "conversation_id": str(uuid.uuid4()),
                "user_message": "hi",
                "rewritten_query": "",
                "retrieved_chunks": [],
                "reranked_chunks": [],
                "messages": [],
                "answer": "",
                "early_exit": False,
            })

        assert result["early_exit"] is True
        assert "no documents" in result["answer"].lower()

    async def test_early_exit_when_collection_not_found(self):
        from app.chat.graph import collection_router

        mock_client = AsyncMock()
        mock_client.get_collection = AsyncMock(side_effect=Exception("not found"))

        with patch("app.chat.graph.get_chroma_client", AsyncMock(return_value=mock_client)):
            result = await collection_router({
                "collection_id": str(uuid.uuid4()),
                "conversation_id": str(uuid.uuid4()),
                "user_message": "hi",
                "rewritten_query": "",
                "retrieved_chunks": [],
                "reranked_chunks": [],
                "messages": [],
                "answer": "",
                "early_exit": False,
            })

        assert result["early_exit"] is True

    async def test_continues_when_collection_has_documents(self):
        from app.chat.graph import collection_router

        mock_collection = AsyncMock()
        mock_collection.count = AsyncMock(return_value=5)
        mock_client = AsyncMock()
        mock_client.get_collection = AsyncMock(return_value=mock_collection)

        with patch("app.chat.graph.get_chroma_client", AsyncMock(return_value=mock_client)):
            result = await collection_router({
                "collection_id": str(uuid.uuid4()),
                "conversation_id": str(uuid.uuid4()),
                "user_message": "hi",
                "rewritten_query": "",
                "retrieved_chunks": [],
                "reranked_chunks": [],
                "messages": [],
                "answer": "",
                "early_exit": False,
            })

        assert result["early_exit"] is False


@pytest.mark.unit
class TestQueryRewriter:
    async def test_skips_rewrite_on_first_message(self):
        from app.chat.graph import query_rewriter

        state = {
            "collection_id": str(uuid.uuid4()),
            "conversation_id": str(uuid.uuid4()),
            "user_message": "What is Python?",
            "rewritten_query": "",
            "retrieved_chunks": [],
            "reranked_chunks": [],
            "messages": [],
            "answer": "",
            "early_exit": False,
        }

        result = await query_rewriter(state)

        assert result["rewritten_query"] == "What is Python?"

    async def test_rewrites_when_history_present(self):
        from app.chat.graph import query_rewriter

        mock_llm = AsyncMock()
        mock_llm.astream = AsyncMock()

        mock_settings = MagicMock()
        mock_chain_output = "What is Python programming language?"

        with patch("app.chat.graph.get_settings", return_value=mock_settings), \
             patch("app.chat.graph.get_llm", return_value=MagicMock()), \
             patch("langchain_core.runnables.base.RunnableSequence.ainvoke",
                   AsyncMock(return_value=mock_chain_output)):
            result = await query_rewriter({
                "collection_id": str(uuid.uuid4()),
                "conversation_id": str(uuid.uuid4()),
                "user_message": "Tell me more about it",
                "rewritten_query": "",
                "retrieved_chunks": [],
                "reranked_chunks": [],
                "messages": [
                    {"role": "user", "content": "What is Python?"},
                    {"role": "assistant", "content": "Python is a programming language."},
                ],
                "answer": "",
                "early_exit": False,
            })

        assert "rewritten_query" in result


@pytest.mark.unit
class TestRetriever:
    async def test_early_exit_when_no_results(self):
        from app.chat.graph import retriever

        mock_collection = AsyncMock()
        mock_collection.query = AsyncMock(return_value={"metadatas": [[]]})
        mock_client = AsyncMock()
        mock_client.get_collection = AsyncMock(return_value=mock_collection)

        mock_embeddings = MagicMock()
        mock_embeddings.embed_query = MagicMock(return_value=[0.1, 0.2])

        with patch("app.chat.graph.get_chroma_client", AsyncMock(return_value=mock_client)), \
             patch("app.chat.graph.get_embeddings", return_value=mock_embeddings), \
             patch("app.chat.graph.get_settings", return_value=MagicMock()):
            result = await retriever({
                "collection_id": str(uuid.uuid4()),
                "conversation_id": str(uuid.uuid4()),
                "user_message": "query",
                "rewritten_query": "query",
                "retrieved_chunks": [],
                "reranked_chunks": [],
                "messages": [],
                "answer": "",
                "early_exit": False,
            })

        assert result["early_exit"] is True
        assert result["retrieved_chunks"] == []

    async def test_returns_deduplicated_parent_texts(self):
        from app.chat.graph import retriever

        mock_collection = AsyncMock()
        mock_collection.query = AsyncMock(return_value={
            "metadatas": [[
                {"parent_id": "p1", "parent_text": "Parent one"},
                {"parent_id": "p1", "parent_text": "Parent one"},  # duplicate
                {"parent_id": "p2", "parent_text": "Parent two"},
            ]]
        })
        mock_client = AsyncMock()
        mock_client.get_collection = AsyncMock(return_value=mock_collection)

        mock_embeddings = MagicMock()
        mock_embeddings.embed_query = MagicMock(return_value=[0.1, 0.2])

        with patch("app.chat.graph.get_chroma_client", AsyncMock(return_value=mock_client)), \
             patch("app.chat.graph.get_embeddings", return_value=mock_embeddings), \
             patch("app.chat.graph.get_settings", return_value=MagicMock()):
            result = await retriever({
                "collection_id": str(uuid.uuid4()),
                "conversation_id": str(uuid.uuid4()),
                "user_message": "query",
                "rewritten_query": "query",
                "retrieved_chunks": [],
                "reranked_chunks": [],
                "messages": [],
                "answer": "",
                "early_exit": False,
            })

        assert result["early_exit"] is False
        assert result["retrieved_chunks"] == ["Parent one", "Parent two"]


@pytest.mark.unit
class TestRerankerNode:
    async def test_calls_rerank_and_returns_chunks(self):
        from app.chat.graph import reranker_node

        with patch("app.chat.graph.rerank", return_value=["best chunk"]):
            result = await reranker_node({
                "collection_id": str(uuid.uuid4()),
                "conversation_id": str(uuid.uuid4()),
                "user_message": "query",
                "rewritten_query": "rewritten query",
                "retrieved_chunks": ["chunk a", "chunk b"],
                "reranked_chunks": [],
                "messages": [],
                "answer": "",
                "early_exit": False,
            })

        assert result["reranked_chunks"] == ["best chunk"]


@pytest.mark.unit
class TestConditionalRouting:
    def test_route_after_collection_exits_on_early_exit(self):
        from app.chat.graph import _route_after_collection
        from langgraph.graph import END

        result = _route_after_collection({"early_exit": True})
        assert result == END

    def test_route_after_collection_continues_normally(self):
        from app.chat.graph import _route_after_collection

        result = _route_after_collection({"early_exit": False})
        assert result == "query_rewriter"

    def test_route_after_retriever_exits_on_early_exit(self):
        from app.chat.graph import _route_after_retriever
        from langgraph.graph import END

        result = _route_after_retriever({"early_exit": True})
        assert result == END

    def test_route_after_retriever_continues_normally(self):
        from app.chat.graph import _route_after_retriever

        result = _route_after_retriever({"early_exit": False})
        assert result == "reranker"
