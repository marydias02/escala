"""add po_code, migo_ref and added_in_sap_timestamp to sap_processes

Revision ID: 20260825_01
Revises: 20260821_02
Create Date: 2026-08-25 00:00:00.000000

po_code and migo_ref close the gap flagged by MissingSapColumnError in
non_conformities_resolution.handlers (missing_po, missing_migo, amount_mismatch):
those handlers write the buyer-provided PO code / discovered MIGO reference to SAP
but had no column to persist them locally.

added_in_sap_timestamp records when SAP first created the process, independent of
last_interaction_datetime (which tracks our own back-and-forth with the buyer, not
the process's origin). The validation big-numbers endpoint buckets its weekly
metrics by this column rather than by any local received-at time, since that is
what the business considers a process's "week received".
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260825_01'
down_revision: Union[str, Sequence[str], None] = '20260821_02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("sap_processes", sa.Column("po_code", sa.String(length=10), nullable=True))
    op.add_column("sap_processes", sa.Column("migo_ref", sa.String(length=50), nullable=True))
    op.add_column(
        "sap_processes", sa.Column("added_in_sap_timestamp", sa.TIMESTAMP(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("sap_processes", "added_in_sap_timestamp")
    op.drop_column("sap_processes", "migo_ref")
    op.drop_column("sap_processes", "po_code")
