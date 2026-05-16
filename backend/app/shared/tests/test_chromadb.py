import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.unit
class TestGetChromaClientSingleton:
    async def test_returns_same_instance_on_repeated_calls(self):
        import app.shared.chromadb as chromadb_module

        mock_client = MagicMock()
        chromadb_module._client = None

        with patch("app.shared.chromadb.chromadb.AsyncHttpClient", new=AsyncMock(return_value=mock_client)):
            c1 = await chromadb_module.get_chroma_client()
            c2 = await chromadb_module.get_chroma_client()

        assert c1 is c2 is mock_client

        chromadb_module._client = None

    async def test_initialises_with_settings(self):
        import app.shared.chromadb as chromadb_module

        chromadb_module._client = None
        mock_client = MagicMock()

        with patch("app.shared.chromadb.chromadb.AsyncHttpClient", new=AsyncMock(return_value=mock_client)) as mock_factory:
            await chromadb_module.get_chroma_client()

        mock_factory.assert_called_once_with(host="chromadb", port=8001)

        chromadb_module._client = None


@pytest.mark.integration
class TestChromaDBIntegration:
    async def test_heartbeat_succeeds(self):
        import chromadb as chroma

        client = await chroma.AsyncHttpClient(host="chromadb", port=8001)
        result = await client.heartbeat()
        assert isinstance(result, int)
