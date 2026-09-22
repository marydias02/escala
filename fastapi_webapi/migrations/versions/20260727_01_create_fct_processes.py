"""create fct_processes

Revision ID: 20260727_01
Revises: 
Create Date: 2026-07-27 15:27:22.092764

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '20260727_01'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "fct_processes",
        sa.Column(
            "process_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("sender_email", sa.String(length=320), nullable=False),
        sa.Column("email_subject", sa.Text(), nullable=True),
        sa.Column("email_content", sa.Text(), nullable=True),
        sa.Column("reception_date", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("fct_processes")
