"""create sap_messages and sap_processes tables

Revision ID: 20260821_02
Revises: 20260821_01
Create Date: 2026-08-21 00:00:00.000000

sap_messages and sap_processes mirror SAP-side records: message log entries
exchanged during a process, and the reconciliation status of each SAP process
itself. sap_processes.doc_id is an optional link back to fct_documents when a
process has been matched to an extracted document.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '20260821_02'
down_revision: Union[str, Sequence[str], None] = '20260821_01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "sap_messages",
        sa.Column("internal_id", sa.String(length=50), primary_key=True),
        sa.Column("timestamp", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("sender", sa.String(length=100), nullable=True),
        sa.Column("recipient", sa.String(length=100), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("process_ref_no", sa.String(length=50), nullable=True),
    )

    op.create_table(
        "sap_processes",
        sa.Column("reference_no", sa.String(length=50), primary_key=True),
        sa.Column("supplier_id", sa.String(length=10), nullable=False),
        sa.Column("bu_id", sa.String(length=4), nullable=False),
        sa.Column(
            "doc_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fct_documents.document_id"),
            nullable=True,
        ),
        sa.Column("total_amount", sa.Float(), nullable=True),
        sa.Column("document_date", sa.Date(), nullable=True),
        sa.Column("is_financial", sa.Boolean(), nullable=True),
        sa.Column("last_interaction", sa.String(length=100), nullable=True),
        sa.Column("last_interaction_datetime", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("issue", sa.String(length=100), nullable=True),
        sa.Column("owner", sa.String(length=100), nullable=True),
        sa.Column("reconciled", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("sap_processes")
    op.drop_table("sap_messages")
