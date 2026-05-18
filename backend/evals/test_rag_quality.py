"""RAGAS evaluation test.

Measures faithfulness and answer relevancy of the end-to-end RAG pipeline
using a pre-generated testset (evals/testset.json).

Run manually or in a nightly CI job — never on every PR:

    cd backend
    OPENAI_API_KEY=sk-... pytest -m eval evals/test_rag_quality.py -v -s

Requires:
    - OPENAI_API_KEY env var (used for ingestion embeddings, LLM generation, and RAGAS judge)
    - Docker (testcontainers spin up Postgres + ChromaDB)
    - testset.json committed to evals/ (generate with evals/generate_testset.py)
"""
import json
import uuid
from pathlib import Path

import pytest

TESTSET_PATH = Path(__file__).parent / "testset.json"
SAMPLE_DOC = Path(__file__).parent / "sample_docs" / "knowledge.txt"


@pytest.mark.eval
class TestRagQuality:
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

                pg_url = pg.get_connection_url().replace(
                    "postgresql+psycopg2://", "postgresql+asyncpg://"
                )
                monkeypatch.setenv("POSTGRES_URL", pg_url)
                monkeypatch.setenv("CHROMADB_HOST", chroma_host)
                monkeypatch.setenv("CHROMADB_PORT", str(chroma_port))
                # Use OpenAI for both embeddings and LLM so the full pipeline
                # works without Ollama, and retrieval vectors actually match.
                monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
                monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-3-small")
                monkeypatch.setenv("LLM_PROVIDER", "openai")

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

    async def test_faithfulness_and_answer_relevancy(self):
        from openai import AsyncOpenAI, OpenAI

        from ragas import EvaluationDataset, SingleTurnSample, evaluate
        from ragas.embeddings import OpenAIEmbeddings
        from ragas.llms import llm_factory
        from ragas.metrics.collections import AnswerRelevancy, Faithfulness

        from app.chat.graph import graph
        from app.knowledge.schemas import CollectionCreate
        from app.knowledge.service import create_collection, ingest_document
        from app.shared.config import get_settings
        from app.shared.database import _get_session_factory

        if not TESTSET_PATH.exists():
            pytest.skip(
                f"testset.json not found at {TESTSET_PATH}. "
                "Run `python -m evals.generate_testset` to generate it."
            )

        testset = json.loads(TESTSET_PATH.read_text())
        if not testset:
            pytest.skip("testset.json is empty.")

        settings = get_settings()
        api_key = settings.openai_api_key or None  # falls back to OPENAI_API_KEY env var if empty

        async with _get_session_factory()() as db:
            collection = await create_collection(db, CollectionCreate(name="eval-col"))

        doc_bytes = SAMPLE_DOC.read_bytes()

        async with _get_session_factory()() as db:
            await ingest_document(db, collection.id, doc_bytes, "knowledge.txt")

        samples = []
        for item in testset:
            question = item["user_input"]
            initial_state = {
                "collection_id": str(collection.id),
                "conversation_id": str(uuid.uuid4()),
                "user_message": question,
                "rewritten_query": "",
                "retrieved_chunks": [],
                "reranked_chunks": [],
                "messages": [],
                "answer": "",
                "early_exit": False,
            }
            final_state = await graph.ainvoke(initial_state)
            samples.append(
                SingleTurnSample(
                    user_input=question,
                    response=final_state["answer"],
                    retrieved_contexts=final_state["reranked_chunks"] or [""],
                )
            )

        judge_llm = llm_factory("gpt-4o-mini", client=OpenAI(api_key=api_key))
        judge_embeddings = OpenAIEmbeddings(client=AsyncOpenAI(api_key=api_key))

        dataset = EvaluationDataset(samples=samples)
        results = evaluate(
            dataset=dataset,
            metrics=[
                Faithfulness(llm=judge_llm),
                AnswerRelevancy(llm=judge_llm, embeddings=judge_embeddings),
            ],
        )

        print("\n=== RAGAS Scores ===")
        print(results)
        # No threshold assertion — scores are informational until a baseline is established.
