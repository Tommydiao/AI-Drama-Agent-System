"""Create the canonical PostgreSQL schema.

Revision ID: 20260831_0001
Revises: None
"""
from __future__ import annotations

from alembic import op

from app.db import metadata


revision = "20260831_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in metadata.sorted_tables:
        table.create(bind=bind, checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(metadata.sorted_tables):
        table.drop(bind=bind, checkfirst=False)
