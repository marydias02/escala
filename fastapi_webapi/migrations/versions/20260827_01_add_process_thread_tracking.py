"""add thread tracking, email_status and email_action to fct_processes

Revision ID: 20260827_01
Revises: 20260825_01
Create Date: 2026-08-27 00:00:00.000000

thread_id is the Graph conversationId, recorded per process so the emails of one
supplier thread can be grouped after the fact. Tracking only for now — dedup
stays keyed on message_id. Non-unique index, unlike message_id's: several
processes sharing a thread_id is the expected shape.

thread_message_count is this email's position in its thread (1 for the first
ingested, 2 for the second, ...), frozen at insert rather than recomputed, so
earlier rows never need rewriting. From THREAD_ESCALATION_COUNT on it stops the
pipeline replying or forwarding, handing the email to a human instead.

email_status and email_action are the two axes of `decisions.decide_email`, and
are stored separately because they answer different questions. email_action is
what the email warrants ("Retornado ao Fornecedor", ...) and is a LIST: one email
can owe a supplier reply for one document and a treasury forward for another.
email_status is the process lifecycle — "Aberto" or "Fechado" — i.e. whether
anyone still owes the email anything.

ARRAY(Text) for email_action mirrors fct_documents.alerts_list. Unlike that
column it is nullable with no '{}' default: fct_processes has existing rows, and
NULL says "never decided", which an empty array would misreport as "decided,
warranted nothing".

All four are NULL for rows written before this migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '20260827_01'
down_revision: Union[str, Sequence[str], None] = '20260825_01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("fct_processes", sa.Column("thread_id", sa.Text(), nullable=True))
    op.add_column("fct_processes", sa.Column("thread_message_count", sa.Integer(), nullable=True))
    op.add_column("fct_processes", sa.Column("email_status", sa.String(length=100), nullable=True))
    op.add_column(
        "fct_processes",
        sa.Column("email_action", postgresql.ARRAY(sa.Text()), nullable=True),
    )
    op.create_index("ix_fct_processes_thread_id", "fct_processes", ["thread_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_fct_processes_thread_id", table_name="fct_processes")
    op.drop_column("fct_processes", "email_action")
    op.drop_column("fct_processes", "email_status")
    op.drop_column("fct_processes", "thread_message_count")
    op.drop_column("fct_processes", "thread_id")
