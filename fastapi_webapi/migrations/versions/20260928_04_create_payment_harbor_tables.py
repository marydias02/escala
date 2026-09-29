"""create payment-harbor and payment-email tables

Revision ID: 20260928_04
Revises: 20260928_03
Create Date: 2026-09-28 00:00:00.000000

Separate payment-email tables use the ``_harbor`` suffix for the sync-run
table because ``email_sync_runs`` already exists. All fields are required.
``invoice_matching.invoice_id`` references the unique invoice primary key.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260928_04"
down_revision: str | Sequence[str] | None = "20260928_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "fct_payments",
        sa.Column("payment_id", sa.String(50), primary_key=True),
        sa.Column("transfer_reference", sa.String(50), nullable=False),
        sa.Column("bu_id", sa.String(4), nullable=False),
        sa.Column("account", sa.String(20), nullable=False),
        sa.Column("source_bank_account", sa.String(20), nullable=False),
        sa.Column("description", sa.String(100), nullable=False),
        sa.Column("additional_info", sa.Text(), nullable=False),
        sa.Column("entry_type", sa.String(50), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("is_treasury", sa.Boolean(), nullable=False),
        sa.Column("decision", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
    )
    op.create_index("ix_fct_payments_bu_id", "fct_payments", ["bu_id"])

    op.create_table(
        "email_sync_runs_harbor",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("mailbox", sa.Text(), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("sync_url", sa.Text(), nullable=False),
        sa.Column("last_received_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("resynced", sa.Boolean(), nullable=False),
        sa.Column("pages_fetched", sa.Integer(), nullable=False),
        sa.Column("messages_seen", sa.Integer(), nullable=False),
        sa.Column("messages_new", sa.Integer(), nullable=False),
        sa.Column("messages_processed", sa.Integer(), nullable=False),
        sa.Column("messages_failed", sa.Integer(), nullable=False),
        sa.Column("messages_gone", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
    )

    op.create_table(
        "payment_email_messages",
        sa.Column("message_id", sa.Text(), primary_key=True),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("sender_email", sa.String(320), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=False),
        sa.Column("first_seen_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_sync_runs_harbor.run_id"), nullable=False),
        sa.Column("processed_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_sync_runs_harbor.run_id"), nullable=False),
        sa.Column("process_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fct_processes.process_id"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    op.create_table(
        "payment_email_information",
        sa.Column("payment_information_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", sa.Text(), sa.ForeignKey("payment_email_messages.message_id"), nullable=False),
        sa.Column("is_payment_related", sa.Boolean(), nullable=False),
        sa.Column("payment_note_code", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("extraction_content", postgresql.JSONB(), nullable=False),
        sa.Column("body_pdf_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    op.create_table(
        "payment_notes",
        sa.Column("payment_note_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("payment_note_code", sa.String(20), nullable=False),
        sa.Column("document_number", sa.Text(), nullable=False),
        sa.Column("value_paid", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("total_payment_note", sa.Float(), nullable=False),
        sa.Column("message_id", sa.Text(), sa.ForeignKey("payment_email_messages.message_id"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("extracted_content", postgresql.JSONB(), nullable=False),
    )

    op.create_table(
        "payment_analysis",
        sa.Column("payment_id", sa.String(50), sa.ForeignKey("fct_payments.payment_id"), nullable=False),
        sa.Column("payment_note_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payment_notes.payment_note_id"), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("payment_id", "payment_note_id"),
    )

    op.create_table(
        "invoice_matching",
        sa.Column("invoice_id", sa.String(24), sa.ForeignKey("fct_invoices.invoice_id"), nullable=False),
        sa.Column("payment_id", sa.String(50), sa.ForeignKey("fct_payments.payment_id"), nullable=False),
        sa.Column("invoice_pending_value", sa.Float(), nullable=False),
        sa.Column("matched_value", sa.Float(), nullable=False),
        sa.Column("final_pending_value", sa.Float(), nullable=False),
        sa.Column("matched_currency", sa.String(3), nullable=False),
        sa.PrimaryKeyConstraint("invoice_id", "payment_id"),
    )
    op.create_index("ix_invoice_matching_invoice_id", "invoice_matching", ["invoice_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_invoice_matching_invoice_id", table_name="invoice_matching")
    op.drop_table("invoice_matching")
    op.drop_table("payment_analysis")
    op.drop_table("payment_notes")
    op.drop_table("payment_email_information")
    op.drop_table("payment_email_messages")
    op.drop_table("email_sync_runs_harbor")
    op.drop_index("ix_fct_payments_bu_id", table_name="fct_payments")
    op.drop_table("fct_payments")
