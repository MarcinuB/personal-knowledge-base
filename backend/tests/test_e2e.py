"""
End-to-end tests that run against a live Docker Compose stack.

Run with: pytest -m e2e
Skip automatically when the stack isn't running.
"""

import json
import uuid
from pathlib import Path

import httpx
import pytest

# All tests in this module share a single session-scoped event loop so that
# the session-scoped httpx.AsyncClient is usable from every test function.
pytestmark = pytest.mark.asyncio(loop_scope="session")

BASE_URL = "http://localhost:8000"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
INGREDIENTS = ["butter", "sugar", "flour", "eggs", "chocolate", "vanilla"]


async def collect_sse_tokens(response: httpx.Response) -> tuple[str, dict]:
    tokens: list[str] = []
    done_event: dict = {}
    async for line in response.aiter_lines():
        if not line.startswith("data:"):
            continue
        payload = json.loads(line[len("data:") :].strip())
        if payload["type"] == "token":
            tokens.append(payload["content"])
        elif payload["type"] == "done":
            done_event = payload
        elif payload["type"] == "error":
            pytest.fail(f"SSE error from server: {payload['content']}")
    return "".join(tokens), done_event


@pytest.fixture(scope="session", loop_scope="session")
async def client():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120.0) as c:
        try:
            resp = await c.get("/health")
            resp.raise_for_status()
        except (httpx.ConnectError, httpx.ConnectTimeout):
            pytest.skip("Docker Compose stack is not running — skipping e2e tests")
        yield c


@pytest.fixture(scope="session", loop_scope="session")
async def e2e_collection(client: httpx.AsyncClient) -> str:
    name = f"e2e-{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/api/collections",
        json={"name": name, "description": "E2E test collection"},
    )
    assert resp.status_code == 201
    collection_id = resp.json()["id"]

    recipe_bytes = (FIXTURES_DIR / "sample_recipe.txt").read_bytes()
    upload_resp = await client.post(
        f"/api/collections/{collection_id}/documents",
        files={"file": ("sample_recipe.txt", recipe_bytes, "text/plain")},
    )
    assert upload_resp.status_code == 201
    assert upload_resp.json()["status"] == "ready", (
        f"Document did not reach ready status: {upload_resp.json()}"
    )

    yield collection_id

    await client.delete(f"/api/collections/{collection_id}")


@pytest.mark.e2e
async def test_ingest_and_query(client: httpx.AsyncClient, e2e_collection: str):
    conv_resp = await client.post(
        "/api/conversations",
        json={"collection_id": e2e_collection},
    )
    assert conv_resp.status_code == 201
    conversation_id = conv_resp.json()["id"]

    async with client.stream(
        "POST",
        "/api/chat",
        json={"conversation_id": conversation_id, "message": "What are the ingredients in the recipe?"},
    ) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        full_text, done = await collect_sse_tokens(response)

    assert any(ingredient in full_text.lower() for ingredient in INGREDIENTS), (
        f"Expected an ingredient name in response, got: {full_text!r}"
    )
    assert done.get("conversation_id") == conversation_id


@pytest.mark.e2e
async def test_multi_turn_followup(client: httpx.AsyncClient, e2e_collection: str):
    conv_resp = await client.post(
        "/api/conversations",
        json={"collection_id": e2e_collection},
    )
    assert conv_resp.status_code == 201
    conversation_id = conv_resp.json()["id"]

    # First turn — establishes context
    async with client.stream(
        "POST",
        "/api/chat",
        json={"conversation_id": conversation_id, "message": "What are the ingredients in the recipe?"},
    ) as response:
        assert response.status_code == 200
        await collect_sse_tokens(response)

    # Second turn — ambiguous follow-up, requires query rewriting to be meaningful
    async with client.stream(
        "POST",
        "/api/chat",
        json={"conversation_id": conversation_id, "message": "How much butter do I need?"},
    ) as response:
        assert response.status_code == 200
        full_text, done = await collect_sse_tokens(response)

    assert "butter" in full_text.lower() or any(ch.isdigit() for ch in full_text), (
        f"Expected butter quantity in follow-up response, got: {full_text!r}"
    )
    assert done.get("conversation_id") == conversation_id


@pytest.mark.e2e
async def test_i_dont_know_path(client: httpx.AsyncClient):
    name = f"e2e-empty-{uuid.uuid4().hex[:8]}"
    col_resp = await client.post("/api/collections", json={"name": name})
    assert col_resp.status_code == 201
    collection_id = col_resp.json()["id"]

    try:
        conv_resp = await client.post(
            "/api/conversations",
            json={"collection_id": collection_id},
        )
        assert conv_resp.status_code == 201
        conversation_id = conv_resp.json()["id"]

        async with client.stream(
            "POST",
            "/api/chat",
            json={"conversation_id": conversation_id, "message": "What does the document say?"},
        ) as response:
            assert response.status_code == 200
            full_text, _ = await collect_sse_tokens(response)

        assert len(full_text) > 0, "Expected a graceful response from empty collection, got empty string"
    finally:
        await client.delete(f"/api/collections/{collection_id}")


@pytest.mark.e2e
async def test_document_upload_status(client: httpx.AsyncClient):
    name = f"e2e-upload-{uuid.uuid4().hex[:8]}"
    col_resp = await client.post("/api/collections", json={"name": name})
    assert col_resp.status_code == 201
    collection_id = col_resp.json()["id"]

    try:
        recipe_bytes = (FIXTURES_DIR / "sample_recipe.txt").read_bytes()
        upload_resp = await client.post(
            f"/api/collections/{collection_id}/documents",
            files={"file": ("sample_recipe.txt", recipe_bytes, "text/plain")},
        )
        assert upload_resp.status_code == 201
        doc = upload_resp.json()
        assert doc["status"] == "ready"
        assert doc["filename"] == "sample_recipe.txt"
    finally:
        await client.delete(f"/api/collections/{collection_id}")
