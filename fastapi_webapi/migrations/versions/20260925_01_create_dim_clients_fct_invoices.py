"""create dim_clients and fct_invoices, filled by the lakehouse ETL

Revision ID: 20260925_01
Revises: 20260921_01
Create Date: 2026-09-25 00:00:00.000000

dim_clients: the BUT000 partners SAP posts or bills to as customers, keyed by
the SAP partner number. The lakehouse has no customer master (KNA1) yet, so
`vat` comes from the latest billing document (VBRK) or, failing that, the
partner's supplier record (LFA1); `vat_source` says which. It gets the same
generated search columns as dim_suppliers (see 20260918_02).

fct_invoices: OPEN customer items only — the ETL deletes a row once SAP clears
it. Keyed by `invoice_id` = "bu_id/fiscal_year/document_nr/line", since a
document number is only unique within its company code and fiscal year. As
replicated today the source (BSEG) carries special G/L 'E' items only; it moves
to BSID/BKPF once those are replicated. No FK to dim_clients, same as
fct_purchase_orders: the feeds can land out of order.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260925_01"
down_revision: str | Sequence[str] | None = "20260921_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Same expressions as 20260918_02, so search treats clients like suppliers.
_VAT_NORM = "upper(regexp_replace(vat, '[^A-Za-z0-9]', '', 'g'))"

_INDEXES = (
    ("ix_dim_clients_name_norm_trgm", "dim_clients", "USING gin (name_norm gin_trgm_ops)"),
    ("ix_dim_clients_id_norm", "dim_clients", "(id_norm text_pattern_ops)"),
    ("ix_dim_clients_vat_norm", "dim_clients", "(vat_norm text_pattern_ops)"),
    ("ix_dim_clients_vat_core", "dim_clients", "(vat_core text_pattern_ops)"),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "dim_clients",
        sa.Column("client_id", sa.String(length=10), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("vat", sa.String(length=20), nullable=True),
        sa.Column("vat_source", sa.String(length=4), nullable=True),  # 'VBRK' | 'LFA1'
    )
    op.execute(
        f"""
        ALTER TABLE dim_clients
            ADD COLUMN id_norm text GENERATED ALWAYS AS
                (coalesce(nullif(ltrim(client_id, '0'), ''), '0')) STORED,
            ADD COLUMN vat_norm text GENERATED ALWAYS AS ({_VAT_NORM}) STORED,
            ADD COLUMN vat_core text GENERATED ALWAYS AS
                (nullif(regexp_replace({_VAT_NORM}, '^[A-Z]{{2}}(?=[A-Z0-9])', ''), '')) STORED,
            ADD COLUMN name_norm text GENERATED ALWAYS AS (public.f_search_norm(name)) STORED
        """
    )
    for name, table, definition in _INDEXES:
        op.execute(f"CREATE INDEX {name} ON {table} {definition}")

    op.create_table(
        "fct_invoices",
        sa.Column("invoice_id", sa.String(length=24), primary_key=True),
        sa.Column("bu_id", sa.String(length=4), nullable=False),
        sa.Column("fiscal_year", sa.String(length=4), nullable=False),
        sa.Column("document_nr", sa.String(length=10), nullable=False),
        sa.Column("line", sa.String(length=3), nullable=False),
        sa.Column("client_id", sa.String(length=10), nullable=False),
        sa.Column("document_type", sa.String(length=2), nullable=True),
        # Original document of an SAPF103 re-posting, read from the assignment.
        sa.Column("original_document_nr", sa.String(length=10), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        # Precision matches the source BSEG.WRBTR Decimal(23,2).
        sa.Column("total_amount", sa.Numeric(precision=23, scale=2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(precision=23, scale=2), nullable=False),
        sa.Column("open_amount", sa.Numeric(precision=23, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=5), nullable=True),  # ISO 4217; SAP WAERS is 5 chars
    )
    op.create_index("ix_fct_invoices_client_id", "fct_invoices", ["client_id"])
    op.create_index("ix_fct_invoices_bu_id", "fct_invoices", ["bu_id"])
    op.create_index("ix_fct_invoices_document_nr", "fct_invoices", ["document_nr"])
    op.create_index("ix_fct_invoices_original_document_nr", "fct_invoices", ["original_document_nr"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_fct_invoices_original_document_nr", table_name="fct_invoices")
    op.drop_index("ix_fct_invoices_document_nr", table_name="fct_invoices")
    op.drop_index("ix_fct_invoices_bu_id", table_name="fct_invoices")
    op.drop_index("ix_fct_invoices_client_id", table_name="fct_invoices")
    op.drop_table("fct_invoices")

    for name, _table, _definition in _INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
    op.drop_table("dim_clients")
