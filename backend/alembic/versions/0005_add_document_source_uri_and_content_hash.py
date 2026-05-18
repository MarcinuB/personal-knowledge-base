"""add document source_uri and content_hash

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("source_uri", sa.String(), nullable=True))
    op.add_column("documents", sa.Column("content_hash", sa.String(), nullable=True))
    op.create_index("ix_documents_collection_source_uri", "documents", ["collection_id", "source_uri"])


def downgrade() -> None:
    op.drop_index("ix_documents_collection_source_uri", table_name="documents")
    op.drop_column("documents", "content_hash")
    op.drop_column("documents", "source_uri")
