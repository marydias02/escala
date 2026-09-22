"""translate fct_documents.action/status values to Portuguese, default status to Criado

Revision ID: 20260817_04
Revises: 20260727_03
Create Date: 2026-08-17 00:00:00.000000

Actions and statuses were English; the business vocabulary is Portuguese.
This renames every existing value in place and switches the `status` default
from 'Created' to 'Criado', matching the new initial status every document
gets in `invoice_extraction.email_pipeline.derive_status`.

'Ingerir em SAP' / 'Retornado ao Fornecedor' each get a follow-up pipeline
that advances a document from 'Criado' to 'Ingerido' / 'Comunicado' once the
SAP ingestion / supplier notification actually happens; that transition is
not part of this migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260817_01'
down_revision: Union[str, Sequence[str], None] = '20260727_03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACTION_RENAMES = {
    "Ingest in SAP": "Ingerir em SAP",
    "Sent back to Supplier": "Retornado ao Fornecedor",
    "Forward to Treasury": "Encaminhar para Tesouraria",
    "Keep in Inbox": "Manter na Caixa de Entrada",
    "Validate Manually": "Validação Manual",
    "Ignore (has original)": "Ignorar (tem original)",
}

_STATUS_RENAMES = {
    "Created": "Criado",
    "Pending": "Criado",
    "Ingested": "Ingerido",
    "Ignored": "Ignorado",
}


def upgrade() -> None:
    for old, new in _ACTION_RENAMES.items():
        op.execute(
            sa.text("UPDATE fct_documents SET action = :new WHERE action = :old")
            .bindparams(new=new, old=old)
        )
    for old, new in _STATUS_RENAMES.items():
        op.execute(
            sa.text("UPDATE fct_documents SET status = :new WHERE status = :old")
            .bindparams(new=new, old=old)
        )

    op.alter_column(
        "fct_documents",
        "status",
        existing_type=sa.String(length=50),
        server_default=sa.text("'Criado'"),
    )


def downgrade() -> None:
    op.alter_column(
        "fct_documents",
        "status",
        existing_type=sa.String(length=50),
        server_default=sa.text("'Created'"),
    )

    for old, new in _STATUS_RENAMES.items():
        op.execute(
            sa.text("UPDATE fct_documents SET status = :old WHERE status = :new")
            .bindparams(old=old, new=new)
        )
    for old, new in _ACTION_RENAMES.items():
        op.execute(
            sa.text("UPDATE fct_documents SET action = :old WHERE action = :new")
            .bindparams(old=old, new=new)
        )
