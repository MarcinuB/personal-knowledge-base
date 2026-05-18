import asyncio
import hashlib
import os
import tempfile
import uuid
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.chunker import chunk_document
from app.knowledge.models import Collection, Document
from app.knowledge.schemas import CollectionCreate, CollectionRead, DocumentRead
from app.shared.chromadb import get_chroma_client
from app.shared.config import get_settings
from app.shared.embeddings import get_embeddings


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


def _parse_file(file_bytes: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        if suffix == ".pdf":
            from langchain_community.document_loaders import PyPDFLoader
            docs = PyPDFLoader(tmp_path).load()
        elif suffix == ".docx":
            from langchain_community.document_loaders import Docx2txtLoader
            docs = Docx2txtLoader(tmp_path).load()
        elif suffix == ".txt":
            from langchain_community.document_loaders import TextLoader
            docs = TextLoader(tmp_path).load()
        else:
            raise ValueError(f"Unsupported file type: {suffix!r}")
        return "\n".join(d.page_content for d in docs)
    finally:
        os.unlink(tmp_path)


async def _find_existing(db: AsyncSession, collection_id: uuid.UUID, source_uri: str) -> Document | None:
    result = await db.execute(
        select(Document).where(
            Document.collection_id == collection_id,
            Document.source_uri == source_uri,
        )
    )
    return result.scalar_one_or_none()


async def _ingest_text(
    db: AsyncSession,
    collection_id: uuid.UUID,
    text: str,
    source_name: str,
    source_type: str = "upload",
    source_uri: str | None = None,
) -> DocumentRead:
    """Chunk, embed, and store text in ChromaDB; create a Document row.

    Implements upsert: skips unchanged content (same hash), replaces changed
    content by writing new chunks first then deleting old ones.
    """
    if source_uri is None:
        source_uri = source_name
    content_hash = hashlib.sha256(text.encode()).hexdigest()

    existing = await _find_existing(db, collection_id, source_uri)
    if existing and existing.content_hash == content_hash:
        return DocumentRead(id=existing.id, filename=existing.filename, status=existing.status)

    doc = Document(
        collection_id=collection_id,
        filename=source_name,
        source_type=source_type,
        status="processing",
        source_uri=source_uri,
        content_hash=content_hash,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    try:
        chunks = chunk_document(text, str(doc.id), str(collection_id))

        embeddings = get_embeddings(get_settings())
        child_texts = [c["child_text"] for c in chunks]
        vectors = await asyncio.to_thread(embeddings.embed_documents, child_texts)

        chroma = await get_chroma_client()
        chroma_col = await chroma.get_or_create_collection(str(collection_id))
        await chroma_col.add(
            ids=[str(uuid.uuid4()) for _ in chunks],
            embeddings=vectors,
            documents=child_texts,
            metadatas=[
                {k: v for k, v in c.items() if k != "child_text"}
                for c in chunks
            ],
        )

        doc.status = "ready"
    except Exception as e:
        print(f"[_ingest_text] error: {e}", flush=True)
        doc.status = "failed"
        raise
    finally:
        await db.commit()

    if existing:
        chroma = await get_chroma_client()
        chroma_col = await chroma.get_or_create_collection(str(collection_id))
        await chroma_col.delete(where={"doc_id": str(existing.id)})
        await db.delete(existing)
        await db.commit()

    return DocumentRead(id=doc.id, filename=doc.filename, status=doc.status)


async def ingest_document(
    db: AsyncSession,
    collection_id: uuid.UUID,
    file_bytes: bytes,
    filename: str,
) -> DocumentRead:
    await get_collection(db, collection_id)  # raises 404 if missing
    text = await asyncio.to_thread(_parse_file, file_bytes, filename)
    return await _ingest_text(db, collection_id, text, filename, source_type="upload")


async def delete_collection(db: AsyncSession, collection_id: uuid.UUID) -> None:
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection = result.scalar_one_or_none()
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    await db.delete(collection)
    await db.commit()

    chroma = await get_chroma_client()
    await chroma.delete_collection(str(collection_id))
