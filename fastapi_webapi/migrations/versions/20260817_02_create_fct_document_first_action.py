"""create fct_document_first_action

Revision ID: 20260817_02
Revises: 20260817_01
Create Date: 2026-08-17 00:00:00.000000

One row per document, written once at day-one persist (see
`EmailPipeline._persist` in invoice_extraction/email_pipeline.py) and never
updated afterwards. `fct_documents.action` is mutated by manual review
(`DocumentsRepository.alter`), so it cannot answer "what was this document's
action when it was first routed" — this table can.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '20260817_02'
down_revision: Union[str, Sequence[str], None] = '20260817_01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "fct_document_first_action",
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fct_documents.document_id"),
            primary_key=True,
        ),
        sa.Column(
            "process_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fct_processes.process_id"),
            nullable=False,
        ),
        sa.Column("first_action", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_fct_document_first_action_process_id",
        "fct_document_first_action",
        ["process_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_fct_document_first_action_process_id",
        table_name="fct_document_first_action",
    )
    op.drop_table("fct_document_first_action")
