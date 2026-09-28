"""drop dim_clients.vat_source: clients now come from KNA1

Revision ID: 20260928_02
Revises: 20260928_01
Create Date: 2026-09-28 00:00:00.000000

KNA1 (the customer master) is now replicated. dim_clients holds every KNA1
customer, not only those posted or billed to, and its VAT is read from KNA1
itself. `vat_source` told apart the two stand-ins — the latest billing
document (VBRK) and the supplier record (LFA1) — and has nothing left to say.
The next ETL run overwrites every row's `vat` from KNA1.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260928_02"
down_revision: str | Sequence[str] | None = "20260928_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("dim_clients", "vat_source")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("dim_clients", sa.Column("vat_source", sa.String(length=4), nullable=True))
