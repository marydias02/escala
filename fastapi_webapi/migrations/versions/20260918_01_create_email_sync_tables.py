"""create email sync tables for the cron-driven inbox ingestion

Revision ID: 20260918_01
Revises: 20260915_01
Create Date: 2026-09-18 00:00:00.000000

The cron path replaces "list the newest N inbox messages and skip the known
ones" with a Graph delta query whose cursor lives in Postgres. Two tables:

- `email_sync_runs` is one row per cron invocation: the run log AND the cursor.
  `sync_url` is whichever of Graph's `@odata.nextLink` / `@odata.deltaLink`
  came back last (both are opaque resumable URLs); `last_received_at` is the
  newest message seen, the lower bound for a replay after the token expires.
  A run starts by copying the newest recorded cursor forward and updates its
  own row after every page, so the next run resumes from the newest row with a
  non-null `sync_url`, whatever that run's status. Nothing else reads the log.

- `email_messages` records every inbox addition the delta stream ever delivered,
  and its processing state. It is written BEFORE processing, so an email is
  never lost when processing throws — a delta stream delivers each addition
  once — and it is the only thing that drives processing. `first_seen_run_id`
  is the run whose delta page delivered it; `processed_run_id` the run that
  last handled it. Both are NULL for messages `email_pipeline --test` handled
  outside any cron run.

`fct_processes` is not altered: its unique `message_id` index stays the hard
dedup guarantee, and a `fct_processes` row is still written only when an email
succeeds. The link goes the other way, via `email_messages.process_id`, whose
`ON DELETE SET NULL` keeps the reprocessing one-liner working:

    DELETE FROM fct_processes WHERE message_id = '...';
    UPDATE email_messages SET status = 'pending', attempts = 0 WHERE message_id = '...';

No backfill from `fct_processes`: production starts from an empty database, so
these tables are only ever filled by the sync itself.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260918_01"
down_revision: str | Sequence[str] | None = "20260915_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "email_sync_runs",
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("mailbox", sa.Text(), nullable=False),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        # The cursor. NULL sync_url = this run never committed a page.
        sa.Column("sync_url", sa.Text(), nullable=True),
        sa.Column("last_received_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("resynced", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("pages_fetched", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("messages_seen", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("messages_new", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("messages_processed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("messages_failed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("messages_gone", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error", sa.Text(), nullable=True),
    )
    # The cursor lookup: newest run for a mailbox that recorded a sync_url.
    op.create_index(
        "ix_email_sync_runs_mailbox_started_at",
        "email_sync_runs",
        ["mailbox", sa.text("started_at DESC")],
    )

    op.create_table(
        "email_messages",
        sa.Column("message_id", sa.Text(), primary_key=True),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("sender_email", sa.String(length=320), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "first_seen_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_sync_runs.run_id"),
            nullable=True,
        ),
        sa.Column(
            "processed_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_sync_runs.run_id"),
            nullable=True,
        ),
        sa.Column(
            "process_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fct_processes.process_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # The Phase B pick: pending/retryable rows, oldest received_at first.
    op.create_index("ix_email_messages_status_received_at", "email_messages", ["status", "received_at"])
    op.create_index("ix_email_messages_process_id", "email_messages", ["process_id"])
    op.create_index("ix_email_messages_first_seen_run_id", "email_messages", ["first_seen_run_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_email_messages_first_seen_run_id", table_name="email_messages")
    op.drop_index("ix_email_messages_process_id", table_name="email_messages")
    op.drop_index("ix_email_messages_status_received_at", table_name="email_messages")
    op.drop_table("email_messages")
    op.drop_index("ix_email_sync_runs_mailbox_started_at", table_name="email_sync_runs")
    op.drop_table("email_sync_runs")
