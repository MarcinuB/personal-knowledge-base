import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat import service
from app.chat.schemas import ConversationCreate, ConversationRead, ConversationSummary
from app.shared.database import get_db

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationRead, status_code=201)
async def create_conversation(data: ConversationCreate, db: AsyncSession = Depends(get_db)):
    return await service.create_conversation(db, data)


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(db: AsyncSession = Depends(get_db)):
    return await service.list_conversations(db)


@router.get("/{conversation_id}", response_model=ConversationRead)
async def get_conversation(conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await service.get_conversation(db, conversation_id)


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await service.delete_conversation(db, conversation_id)
