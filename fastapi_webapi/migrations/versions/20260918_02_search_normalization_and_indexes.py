"""search normalization columns, functions and indexes

Revision ID: 20260918_02
Revises: 20260918_01
Create Date: 2026-09-18 00:00:00.000000

Ranked entity search needs a normalized form of every id, VAT and name to
compare against. Computing it per row inside the query would defeat indexing,
so each form is a STORED generated column written once per row, with its own
index.

CAVEAT: `f_unaccent` is declared IMMUTABLE, which the unaccent dictionary
cannot actually guarantee — if the rules file changes, `name_norm` and its
index drift from the source `name`. The dim tables are truncate-and-reloaded,
so a reseed repairs it; otherwise drop and re-add the column.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260918_02"
down_revision: str | Sequence[str] | None = "20260918_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Generated columns cannot reference other generated columns, so vat_core
# repeats the vat_norm expression instead of building on it.
_VAT_NORM = "upper(regexp_replace(vat, '[^A-Za-z0-9]', '', 'g'))"
_PARTY_TABLES = (("dim_suppliers", "supplier_id"), ("dim_business_units", "bu_id"))

_INDEXES = (
    ("ix_dim_suppliers_name_norm_trgm", "dim_suppliers", "USING gin (name_norm gin_trgm_ops)"),
    ("ix_dim_suppliers_id_norm", "dim_suppliers", "(id_norm text_pattern_ops)"),
    ("ix_dim_suppliers_vat_norm", "dim_suppliers", "(vat_norm text_pattern_ops)"),
    ("ix_dim_suppliers_vat_core", "dim_suppliers", "(vat_core text_pattern_ops)"),
    ("ix_fct_purchase_orders_po_code_trgm", "fct_purchase_orders", "USING gin (po_code gin_trgm_ops)"),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

    # Schema-qualified everywhere so neither function depends on search_path.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.f_unaccent(text)
        RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS
        $$ SELECT public.unaccent('public.unaccent', $1) $$
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.f_search_norm(text)
        RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS
        $$ SELECT nullif(btrim(regexp_replace(public.f_unaccent(lower($1)), '[^a-z0-9]+', ' ', 'g')), '') $$
        """
    )

    for table, id_column in _PARTY_TABLES:
        op.execute(
            f"""
            ALTER TABLE {table}
                ADD COLUMN id_norm text GENERATED ALWAYS AS
                    (coalesce(nullif(ltrim({id_column}, '0'), ''), '0')) STORED,
                ADD COLUMN vat_norm text GENERATED ALWAYS AS ({_VAT_NORM}) STORED,
                ADD COLUMN vat_core text GENERATED ALWAYS AS
                    (nullif(regexp_replace({_VAT_NORM}, '^[A-Z]{{2}}(?=[A-Z0-9])', ''), '')) STORED,
                ADD COLUMN name_norm text GENERATED ALWAYS AS (public.f_search_norm(name)) STORED
            """
        )

    # dim_business_units gets the columns (shared SQL template) but no indexes:
    # it holds tens of rows.
    for name, table, definition in _INDEXES:
        op.execute(f"CREATE INDEX {name} ON {table} {definition}")


def downgrade() -> None:
    """Downgrade schema."""
    for name, _table, _definition in _INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")

    for table, _id_column in _PARTY_TABLES:
        op.execute(
            f"""
            ALTER TABLE {table}
                DROP COLUMN IF EXISTS id_norm,
                DROP COLUMN IF EXISTS vat_norm,
                DROP COLUMN IF EXISTS vat_core,
                DROP COLUMN IF EXISTS name_norm
            """
        )

    op.execute("DROP FUNCTION IF EXISTS public.f_search_norm(text)")
    op.execute("DROP FUNCTION IF EXISTS public.f_unaccent(text)")
    # Extensions stay installed: dropping can fail if anything else depends on them.
