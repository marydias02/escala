"""create fct_documents

Revision ID: 20260727_02
Revises: 20260727_01
Create Date: 2026-07-27 15:40:00.000000

document_content is stored as a single JSONB column with the shape:
    {
        "supplier_name": str,
        "supplier_id": str,
        "supplier_vat": str,
        "bu_name": str,
        "bu_id": str,
        "bu_vat": str,
        "issue_date": date,
        "base_amount": float,
        "vat_amount": float,
        "total_amount": float,
        "currency": str,
        "po_list": list[str],
    }
Validation of this shape is handled in the application layer (Pydantic).

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
