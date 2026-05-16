import uuid
from datetime import datetime

from pydantic import BaseModel


class ConversationCreate(BaseModel):
    collection_id: uuid.UUID
    title: str | None = None


class MessageRead(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationRead(BaseModel):
    id: uuid.UUID
    collection_id: uuid.UUID
    title: str | None
    created_at: datetime
    messages: list[MessageRead] = []

    model_config = {"from_attributes": True}


class ConversationSummary(BaseModel):
    """Lightweight shape for the sidebar — no messages."""
    id: uuid.UUID
    collection_id: uuid.UUID
    title: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
