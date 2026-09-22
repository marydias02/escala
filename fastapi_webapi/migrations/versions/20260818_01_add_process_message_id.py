"""add message_id to fct_processes, cascade deletes on child FKs

Revision ID: 20260818_01
Revises: 20260817_02
Create Date: 2026-08-18 00:00:00.000000

Graph message id is now the only dedup authority for fct_processes; the unique
index gives new rows a hard guarantee a dedup SELECT alone cannot (it races).
NULL for legacy `.msg`-era rows, which Postgres treats as distinct in a unique
index. ON DELETE CASCADE on the three child FKs makes manual reprocessing a
one-liner (`DELETE FROM fct_processes WHERE message_id = '...'`); Postgres
can't alter a delete rule in place, so each FK is dropped and recreated.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260818_01'
down_revision: Union[str, Sequence[str], None] = '20260817_02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("fct_processes", sa.Column("message_id", sa.Text(), nullable=True))
    op.create_index(
        "ix_fct_processes_message_id", "fct_processes", ["message_id"], unique=True
    )

    op.drop_constraint("fct_documents_process_id_fkey", "fct_documents", type_="foreignkey")
    op.create_foreign_key(
        "fct_documents_process_id_fkey",
        "fct_documents",
        "fct_processes",
        ["process_id"],
        ["process_id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "fct_document_first_action_process_id_fkey", "fct_document_first_action", type_="foreignkey"
    )
    op.create_foreign_key(
        "fct_document_first_action_process_id_fkey",
        "fct_document_first_action",
        "fct_processes",
        ["process_id"],
        ["process_id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "fct_document_first_action_document_id_fkey", "fct_document_first_action", type_="foreignkey"
    )
    op.create_foreign_key(
        "fct_document_first_action_document_id_fkey",
        "fct_document_first_action",
        "fct_documents",
        ["document_id"],
        ["document_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fct_document_first_action_document_id_fkey", "fct_document_first_action", type_="foreignkey"
    )
    op.create_foreign_key(
        "fct_document_first_action_document_id_fkey",
        "fct_document_first_action",
        "fct_documents",
        ["document_id"],
        ["document_id"],
    )

    op.drop_constraint(
        "fct_document_first_action_process_id_fkey", "fct_document_first_action", type_="foreignkey"
    )
    op.create_foreign_key(
        "fct_document_first_action_process_id_fkey",
        "fct_document_first_action",
        "fct_processes",
        ["process_id"],
        ["process_id"],
    )

    op.drop_constraint("fct_documents_process_id_fkey", "fct_documents", type_="foreignkey")
    op.create_foreign_key(
        "fct_documents_process_id_fkey",
        "fct_documents",
        "fct_processes",
        ["process_id"],
        ["process_id"],
    )

    op.drop_index("ix_fct_processes_message_id", table_name="fct_processes")
    op.drop_column("fct_processes", "message_id")
