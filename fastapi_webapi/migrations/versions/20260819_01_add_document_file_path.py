"""add file_path to fct_documents

Revision ID: 20260819_01
Revises: 20260818_01
Create Date: 2026-08-19 17:11:00.000000

Local emulation of future blob storage: relative path (email folder name /
PDF filename) under PROCESSED_EMAILS_DIR, written by email_pipeline._persist.
Nullable with no backfill — existing rows never recorded a filename, so they
simply have no PDF available until reprocessed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260819_01'
down_revision: Union[str, Sequence[str], None] = '20260818_01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("fct_documents", sa.Column("file_path", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("fct_documents", "file_path")
