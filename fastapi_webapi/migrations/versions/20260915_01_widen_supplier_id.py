"""widen supplier_id to fit real SAP LIFNR (10-char, zero-padded)

Revision ID: 20260915_01
Revises: 20260827_01
Create Date: 2026-09-15 00:00:00.000000

The dummy seed data used 9-digit supplier ids ("100000001"), so dim_suppliers.
supplier_id and fct_purchase_orders.supplier_id were sized varchar(9). Real SAP
LFA1.LIFNR / EKKO.LIFNR values are zero-padded to 10 characters (e.g.
"0100003539"), which does not fit — widen both columns to varchar(10).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260915_01'
down_revision: Union[str, Sequence[str], None] = '20260827_01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("dim_suppliers", "supplier_id", type_=sa.String(length=10))
    op.alter_column("fct_purchase_orders", "supplier_id", type_=sa.String(length=10))


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("fct_purchase_orders", "supplier_id", type_=sa.String(length=9))
    op.alter_column("dim_suppliers", "supplier_id", type_=sa.String(length=9))
