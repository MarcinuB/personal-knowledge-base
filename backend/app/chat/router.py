import json
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat import service
from app.chat.graph import run_rag_pipeline
from app.chat.schemas import ChatRequest, ConversationCreate, ConversationRead, ConversationSummary
from app.shared.database import get_db, _get_session_factory

router = APIRouter(prefix="/conversations", tags=["conversations"])
chat_router = APIRouter(tags=["chat"])


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


@chat_router.post("/chat")
async def chat(data: ChatRequest, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    # Pre-flight: load conversation (raises 404 if not found) while we still have normal HTTP semantics
    conversation = await service.get_conversation(db, data.conversation_id)
    messages = [{"role": m.role, "content": m.content} for m in conversation.messages]

    return StreamingResponse(
        _stream_chat(data.conversation_id, conversation.collection_id, data.message, messages),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream_chat(
    conversation_id: uuid.UUID,
    collection_id: uuid.UUID,
    user_message: str,
    messages: list[dict],
) -> AsyncGenerator[str, None]:
    # Persist user message in its own short-lived session
    async with _get_session_factory()() as db:
        await service.add_message(db, conversation_id, "user", user_message)

    answer_parts: list[str] = []
    try:
        async for token in run_rag_pipeline(
            collection_id=collection_id,
            conversation_id=conversation_id,
            user_message=user_message,
            messages=messages,
        ):
            answer_parts.append(token)
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"
        return

    # Persist assistant message
    async with _get_session_factory()() as db:
        assistant_msg = await service.add_message(db, conversation_id, "assistant", "".join(answer_parts))

    yield f"data: {json.dumps({'type': 'done', 'conversation_id': str(conversation_id), 'message_id': str(assistant_msg.id)})}\n\n"
