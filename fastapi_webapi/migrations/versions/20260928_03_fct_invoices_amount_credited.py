"""add fct_invoices.amount_credited

Revision ID: 20260928_03
Revises: 20260928_02
Create Date: 2026-09-28 00:00:00.000000

An open credit memo (BSEG posting key 11/12) that references an invoice through
REBZG/REBZJ/REBZZ reduces what the customer owes on it, the same as a partial
payment does. Until now only partial payments were netted, so `open_amount`
overstated about 2.4k invoices. `amount_credited` holds the credit memos apart
from `amount_paid`, and `open_amount` becomes total - paid - credited. Existing
rows start at 0; the next ETL run fills them and recomputes `open_amount`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260928_03"
down_revision: str | Sequence[str] | None = "20260928_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # The default only backfills existing rows; the ETL always writes the column.
    op.add_column(
        "fct_invoices",
        sa.Column("amount_credited", sa.Numeric(precision=23, scale=2), nullable=False, server_default="0"),
    )
    op.alter_column("fct_invoices", "amount_credited", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("fct_invoices", "amount_credited")
