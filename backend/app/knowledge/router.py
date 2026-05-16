import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge import service
from app.knowledge.schemas import CollectionCreate, CollectionRead, DocumentRead
from app.shared.database import get_db

router = APIRouter(prefix="/collections", tags=["collections"])


@router.post("", response_model=CollectionRead, status_code=201)
async def create_collection(data: CollectionCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_collection(db, data)


@router.get("", response_model=list[CollectionRead])
async def list_collections(db: AsyncSession = Depends(get_db)):
    return await service.list_collections(db)


@router.get("/{collection_id}", response_model=CollectionRead)
async def get_collection(collection_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await service.get_collection(db, collection_id)


@router.delete("/{collection_id}", status_code=204)
async def delete_collection(collection_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await service.delete_collection(db, collection_id)


@router.post("/{collection_id}/documents", response_model=DocumentRead, status_code=201)
async def upload_document(
    collection_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    file_bytes = await file.read()
    return await service.ingest_document(db, collection_id, file_bytes, file.filename)
