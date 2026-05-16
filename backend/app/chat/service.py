import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.chat.models import Conversation, Message
from app.chat.schemas import ConversationCreate, ConversationRead, ConversationSummary


async def create_conversation(db: AsyncSession, data: ConversationCreate) -> ConversationRead:
    conversation = Conversation(collection_id=data.collection_id, title=data.title)
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return ConversationRead(
        id=conversation.id,
        collection_id=conversation.collection_id,
        title=conversation.title,
        created_at=conversation.created_at,
        messages=[],
    )


async def list_conversations(db: AsyncSession) -> list[ConversationSummary]:
    result = await db.execute(
        select(Conversation).order_by(Conversation.created_at.desc())
    )
    return [ConversationSummary.model_validate(c) for c in result.scalars()]


async def get_conversation(db: AsyncSession, conversation_id: uuid.UUID) -> ConversationRead:
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationRead.model_validate(conversation)


async def delete_conversation(db: AsyncSession, conversation_id: uuid.UUID) -> None:
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(conversation)
    await db.commit()


async def add_message(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
) -> Message:
    """Append a message to a conversation. Used by the RAG pipeline (issue #10)."""
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    message = Message(conversation_id=conversation_id, role=role, content=content)
    db.add(message)

    # Auto-set title from first user message if not already set
    if role == "user":
        conv_result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
        conversation = conv_result.scalar_one()
        if conversation.title is None:
            conversation.title = content[:80]

    await db.commit()
    await db.refresh(message)
    return message
