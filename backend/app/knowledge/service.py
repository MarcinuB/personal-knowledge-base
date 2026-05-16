import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.models import Collection, Document
from app.knowledge.schemas import CollectionCreate, CollectionRead
from app.shared.chromadb import get_chroma_client


async def create_collection(db: AsyncSession, data: CollectionCreate) -> CollectionRead:
    collection = Collection(name=data.name, description=data.description)
    db.add(collection)
    await db.commit()
    await db.refresh(collection)

    chroma = await get_chroma_client()
    await chroma.get_or_create_collection(str(collection.id))

    return CollectionRead(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        created_at=collection.created_at,
        document_count=0,
    )


async def list_collections(db: AsyncSession) -> list[CollectionRead]:
    result = await db.execute(
        select(Collection, func.count(Document.id).label("document_count"))
        .outerjoin(Document, Document.collection_id == Collection.id)
        .group_by(Collection.id)
        .order_by(Collection.created_at.desc())
    )
    return [
        CollectionRead(
            id=row.Collection.id,
            name=row.Collection.name,
            description=row.Collection.description,
            created_at=row.Collection.created_at,
            document_count=row.document_count,
        )
        for row in result
    ]


async def get_collection(db: AsyncSession, collection_id: uuid.UUID) -> CollectionRead:
    result = await db.execute(
        select(Collection, func.count(Document.id).label("document_count"))
        .outerjoin(Document, Document.collection_id == Collection.id)
        .where(Collection.id == collection_id)
        .group_by(Collection.id)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return CollectionRead(
        id=row.Collection.id,
        name=row.Collection.name,
        description=row.Collection.description,
        created_at=row.Collection.created_at,
        document_count=row.document_count,
    )


async def delete_collection(db: AsyncSession, collection_id: uuid.UUID) -> None:
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection = result.scalar_one_or_none()
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    await db.delete(collection)
    await db.commit()

    chroma = await get_chroma_client()
    await chroma.delete_collection(str(collection_id))
