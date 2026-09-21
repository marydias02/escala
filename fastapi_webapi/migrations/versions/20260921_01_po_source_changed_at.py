"""add fct_purchase_orders.source_changed_at, the lakehouse ETL's cursor

Revision ID: 20260921_01
Revises: 20260918_02
Create Date: 2026-09-21 00:00:00.000000

Holds EKKO.LASTCHANGEDATETIME per row. `MAX(source_changed_at)` is the ETL's
cursor — there is no run-log table. Safe because the pipeline writes PO rows in
ascending order, so the max over committed rows is always a valid resume point.

Nullable: rows from `seed_sap_real_data.py` predate it. MAX() ignores NULLs, so
an existing database cold-starts into one full re-extract that backfills them.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260921_01"
down_revision: str | Sequence[str] | None = "20260918_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Precision matches the source Decimal(21,7) exactly; no float round-trip.
    op.add_column(
        "fct_purchase_orders",
        sa.Column("source_changed_at", sa.Numeric(precision=21, scale=7), nullable=True),
    )
    # DESC NULLS LAST makes the MAX() lookup an index-only scan.
    op.create_index(
        "ix_fct_purchase_orders_source_changed_at",
        "fct_purchase_orders",
        [sa.text("source_changed_at DESC NULLS LAST")],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_fct_purchase_orders_source_changed_at", table_name="fct_purchase_orders")
    op.drop_column("fct_purchase_orders", "source_changed_at")
