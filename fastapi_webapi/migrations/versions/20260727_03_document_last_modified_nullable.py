"""make fct_documents.last_modified_at nullable, drop now() default

Revision ID: 20260727_03
Revises: 20260727_02
Create Date: 2026-07-27 16:10:00.000000

last_modified_at should only be populated by webapp interactions when a human
edits a document. The pipeline never modifies rows, so a pipeline-created row
must read as "never modified": NULL, mirroring last_modified_by (also NULL).
The original now() server_default made every fresh row look modified-at-creation
by nobody, which is contradictory. This drops the default and makes the column
nullable so NULL unambiguously means "never modified since creation".

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260727_03'
down_revision: Union[str, Sequence[str], None] = '20260727_02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the now() default and allow NULL on last_modified_at."""
    op.alter_column(
        "fct_documents",
        "last_modified_at",
        existing_type=sa.TIMESTAMP(timezone=True),
        nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    """Restore the now() default and NOT NULL constraint."""
    op.alter_column(
        "fct_documents",
        "last_modified_at",
        existing_type=sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
