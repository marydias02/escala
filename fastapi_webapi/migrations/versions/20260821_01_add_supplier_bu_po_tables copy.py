"""create dim_suppliers, dim_business_units, and fct_purchase_orders tables

Revision ID: 20260821_01
Revises: 20260819_01
Create Date: 2026-08-21 00:00:00.000000

Suppliers and business units are master data sourced from SAP, keyed by
SAP's own internal id (string, not a generated UUID). fct_purchase_orders
references supplier_id/bu_id without FK constraints since SAP feeds for
suppliers, business units, and purchase orders can land out of order.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260821_01'
down_revision: Union[str, Sequence[str], None] = '20260819_01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "dim_suppliers",
        sa.Column("supplier_id", sa.String(length=9), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("vat", sa.String(length=20), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),  # ISO 3166-1 alpha-2
        sa.Column("preferred_language", sa.String(length=2), nullable=True),  # ISO 639-1
        sa.Column("is_financial", sa.Integer(), nullable=True),
    )

    op.create_table(
        "dim_business_units",
        sa.Column("bu_id", sa.String(length=4), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("vat", sa.String(length=20), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),  # ISO 3166-1 alpha-2
    )

    op.create_table(
        "fct_purchase_orders",
        sa.Column("po_code", sa.String(length=10), primary_key=True),
        sa.Column("supplier_id", sa.String(length=9), nullable=False),
        sa.Column("bu_id", sa.String(length=4), nullable=False),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("value", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),  # ISO 4217
    )
    op.create_index(
        "ix_fct_purchase_orders_supplier_id",
        "fct_purchase_orders",
        ["supplier_id"],
    )
    op.create_index(
        "ix_fct_purchase_orders_bu_id",
        "fct_purchase_orders",
        ["bu_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_fct_purchase_orders_bu_id", table_name="fct_purchase_orders")
    op.drop_index("ix_fct_purchase_orders_supplier_id", table_name="fct_purchase_orders")
    op.drop_table("fct_purchase_orders")
    op.drop_table("dim_business_units")
    op.drop_table("dim_suppliers")
