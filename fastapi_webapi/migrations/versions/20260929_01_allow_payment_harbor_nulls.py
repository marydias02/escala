"""allow nullable payment-harbor fields

Revision ID: 20260929_01
Revises: 20260928_05
Create Date: 2026-09-29 00:00:00.000000

Relax nullability for fields that may be unavailable during payment and email
processing. The harbor sync-run table follows the existing email_sync_runs
nullability pattern.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260929_01"
down_revision: str | Sequence[str] | None = "20260928_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _alter(table: str, column: str, nullable: bool) -> None:
    op.alter_column(table, column, existing_nullable=not nullable, nullable=nullable)


def upgrade() -> None:
    """Upgrade schema."""
    for column in (
        "source_bank_account",
        "description",
        "additional_info",
        "is_treasury",
        "decision",
        "status",
    ):
        _alter("fct_payments", column, True)

    for column in ("finished_at", "sync_url", "last_received_at", "error"):
        _alter("email_sync_runs_harbor", column, True)

    for column in (
        "received_at",
        "last_error",
        "first_seen_run_id",
        "processed_run_id",
        "process_id",
        "created_at",
        "updated_at",
    ):
        _alter("payment_email_messages", column, True)

    for column in (
        "message_id",
        "is_payment_related",
        "payment_note_code",
        "body_pdf_path",
        "updated_at",
    ):
        _alter("payment_email_information", column, True)

    for column in (
        "payment_note_code",
        "document_number",
        "path",
        "message_id",
        "status",
        "extracted_content",
    ):
        _alter("payment_notes", column, True)

    for column in ("evidence", "rationale"):
        _alter("payment_analysis", column, True)


def downgrade() -> None:
    """Downgrade schema."""
    for column in ("rationale", "evidence"):
        _alter("payment_analysis", column, False)

    for column in (
        "extracted_content",
        "status",
        "message_id",
        "path",
        "document_number",
        "payment_note_code",
    ):
        _alter("payment_notes", column, False)

    for column in (
        "updated_at",
        "body_pdf_path",
        "payment_note_code",
        "is_payment_related",
        "message_id",
    ):
        _alter("payment_email_information", column, False)

    for column in (
        "updated_at",
        "created_at",
        "process_id",
        "processed_run_id",
        "first_seen_run_id",
        "last_error",
        "received_at",
    ):
        _alter("payment_email_messages", column, False)

    for column in ("error", "last_received_at", "sync_url", "finished_at"):
        _alter("email_sync_runs_harbor", column, False)

    for column in (
        "status",
        "decision",
        "is_treasury",
        "additional_info",
        "description",
        "source_bank_account",
    ):
        _alter("fct_payments", column, False)
