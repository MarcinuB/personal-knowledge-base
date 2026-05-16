import chromadb
from app.shared.config import get_settings

# chromadb.AsyncHttpClient is a coroutine function (not a class), so lru_cache
# on the factory would cache an unawaited coroutine. We use a module-level
# sentinel instead to achieve the same singleton guarantee.
_client: chromadb.AsyncClientAPI | None = None


async def get_chroma_client() -> chromadb.AsyncClientAPI:
    global _client
    if _client is None:
        settings = get_settings()
        _client = await chromadb.AsyncHttpClient(
            host=settings.chromadb_host,
            port=settings.chromadb_port,
        )
    return _client
