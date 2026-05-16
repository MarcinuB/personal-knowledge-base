"""add document source_type and status

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("source_type", sa.String(), nullable=False, server_default="upload"))
    op.add_column("documents", sa.Column("status", sa.String(), nullable=False, server_default="processing"))


def downgrade() -> None:
    op.drop_column("documents", "status")
    op.drop_column("documents", "source_type")
