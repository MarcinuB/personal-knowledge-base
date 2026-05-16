import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database import Base


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)
    description: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    documents: Mapped[list["Document"]] = relationship(back_populates="collection", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collections.id"), nullable=False)
    filename: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    collection: Mapped["Collection"] = relationship(back_populates="documents")
