import uuid
from datetime import datetime

from pydantic import BaseModel


class CollectionCreate(BaseModel):
    name: str
    description: str | None = None


class CollectionRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    document_count: int

    model_config = {"from_attributes": True}
