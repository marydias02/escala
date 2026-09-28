"""add fct_invoices.billing_document

Revision ID: 20260928_01
Revises: 20260925_01
Create Date: 2026-09-28 00:00:00.000000

BSEG was reloaded on 2026-09-25 with the ordinary open customer items (posting
key 01), not only the special G/L 'E' re-postings 20260925_01 was written for.
Most of them are SD invoices, and the number the customer sees on one — and
quotes when paying — is its SD billing document (BSEG.VBELN). It stands in for
BKPF.XBLNR, which is not replicated. Null on invoices that did not come from SD.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260928_01"
down_revision: str | Sequence[str] | None = "20260925_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("fct_invoices", sa.Column("billing_document", sa.String(length=10), nullable=True))
    op.create_index("ix_fct_invoices_billing_document", "fct_invoices", ["billing_document"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_fct_invoices_billing_document", table_name="fct_invoices")
    op.drop_column("fct_invoices", "billing_document")
