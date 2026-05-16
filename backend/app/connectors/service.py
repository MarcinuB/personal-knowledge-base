from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import BaseConnector
from app.shared.database import _get_session_factory


class _ConnectorState:
    """SQLAlchemy model-free row helper — we use raw SQL via ORM core."""
    pass


class ConnectorService:
    def __init__(self) -> None:
        self._registry: dict[str, BaseConnector] = {}

    # ── registry ──────────────────────────────────────────────────────────────

    def register(self, connector: BaseConnector) -> None:
        if connector.name in self._registry:
            raise ValueError(f"Connector {connector.name!r} is already registered.")
        self._registry[connector.name] = connector

    def list_connectors(self) -> list[BaseConnector]:
        return list(self._registry.values())

    def get(self, name: str) -> BaseConnector:
        connector = self._registry.get(name)
        if connector is None:
            raise KeyError(f"Connector {name!r} is not registered.")
        return connector

    # ── sync ──────────────────────────────────────────────────────────────────

    async def sync(self, connector_name: str, db: AsyncSession) -> int:
        from app.knowledge.service import _ingest_text

        connector = self.get(connector_name)
        collection_id = connector.config.collection_id
        count = 0

        async for doc in connector.sync():
            source_name = doc.metadata.get("source", f"{connector_name}_{count}")
            await _ingest_text(
                db,
                collection_id,
                doc.page_content,
                source_name,
                source_type="connector",
            )
            count += 1

        await _upsert_last_synced(db, connector_name)
        return count

    # ── last_synced_at ────────────────────────────────────────────────────────

    async def get_last_synced_at(self, db: AsyncSession, connector_name: str) -> datetime | None:
        return await _fetch_last_synced(db, connector_name)


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _fetch_last_synced(db: AsyncSession, name: str) -> datetime | None:
    from sqlalchemy import text
    result = await db.execute(
        text("SELECT last_synced_at FROM connector_state WHERE name = :name"),
        {"name": name},
    )
    row = result.first()
    return row[0] if row else None


async def _upsert_last_synced(db: AsyncSession, name: str) -> None:
    from sqlalchemy import text
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.execute(
        text(
            "INSERT INTO connector_state (name, last_synced_at) VALUES (:name, :ts) "
            "ON CONFLICT (name) DO UPDATE SET last_synced_at = EXCLUDED.last_synced_at"
        ),
        {"name": name, "ts": now},
    )
    await db.commit()


# ── module-level singleton ────────────────────────────────────────────────────

connector_service = ConnectorService()
