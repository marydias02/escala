"""create fct_documents

Revision ID: 20260727_02
Revises: 20260727_01
Create Date: 2026-07-27 15:40:00.000000

document_content is stored as a single JSONB column. Each value-bearing field is
either null or a {"value", "confidence"} object, preserving the validator's
confidence score for later review/thresholding:
    {
        "supplier_name": {"value": str, "confidence": float} | None,
        "supplier_id": {"value": str, "confidence": float} | None,
        "supplier_vat": {"value": str, "confidence": float} | None,
        "document_number": {"value": str, "confidence": float} | None,
        "bu_name": {"value": str, "confidence": float} | None,
        "bu_id": {"value": str, "confidence": float} | None,
        "bu_vat": {"value": str, "confidence": float} | None,
        "issue_date": {"value": date, "confidence": float} | None,
        "base_amount": {"value": float, "confidence": float} | None,
        "vat_amount": {"value": float, "confidence": float} | None,
        "total_amount": {"value": float, "confidence": float} | None,
        "currency": {"value": str, "confidence": float} | None,
        "po_list": [{"value": str, "confidence": float}, ...],
    }
Built by build_document_content in invoice_extraction/email_pipeline.py; shape
is validated in the application layer (Pydantic), not enforced by the DB.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '20260727_02'
down_revision: Union[str, Sequence[str], None] = '20260727_01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "fct_documents",
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "process_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fct_processes.process_id"),
            nullable=False,
        ),
        sa.Column("document_type", sa.String(length=100), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default=sa.text("'Created'"),
            nullable=False,
        ),
        sa.Column("document_content", postgresql.JSONB(), nullable=True),
        sa.Column(
            "version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "alerts_list",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=320), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_modified_by", sa.String(length=320), nullable=True),
        sa.Column(
            "last_modified_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_fct_documents_process_id",
        "fct_documents",
        ["process_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_fct_documents_process_id", table_name="fct_documents")
    op.drop_table("fct_documents")
