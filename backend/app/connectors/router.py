from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.service import connector_service
from app.shared.database import get_db

router = APIRouter(prefix="/connectors", tags=["connectors"])


@router.get("")
async def list_connectors(db: AsyncSession = Depends(get_db)) -> list[dict]:
    result = []
    for connector in connector_service.list_connectors():
        last_synced_at = await connector_service.get_last_synced_at(db, connector.name)
        result.append({
            "name": connector.name,
            "source_type": connector.config.source_type,
            "collection_id": str(connector.config.collection_id),
            "last_synced_at": last_synced_at.isoformat() if last_synced_at else None,
        })
    return result


@router.post("/{name}/sync")
async def sync_connector(name: str, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        connector_service.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Connector {name!r} not found.")
    documents_ingested = await connector_service.sync(name, db)
    return {"documents_ingested": documents_ingested}


@router.get("/{name}/health")
async def health_check(name: str) -> dict:
    try:
        connector = connector_service.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Connector {name!r} not found.")
    healthy = await connector.health_check()
    return {"name": name, "healthy": healthy}
