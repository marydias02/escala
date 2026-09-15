"""Read access to SAP tables replicated into the Azure/Fabric Lakehouse.

Mirrors `api.sql.BaseRepository`'s shape (a `__table_name__` class attribute
plus query helpers) but for Delta tables read via polars/deltalake instead of
Postgres via asyncpg. Reads are lazy (`pl.scan_delta`) so filters and column
selection push down to the Delta reader instead of materializing full SAP
tables — some of them (e.g. ACDOCA) are large — for a single lookup.

All methods are synchronous: the Delta/Azure I/O underneath is blocking, and
today's callers (LangChain `@tool` functions invoked via `.invoke()`) are
synchronous too. If a future async call site needs this, wrap the call in
`asyncio.to_thread(...)` rather than making the repository itself async.
"""

from collections.abc import Collection
from typing import Any, Optional

import polars as pl

from config.settings import settings

AVAILABLE_TABLES = ("ACDOCA", "BSAD", "BSEG", "BUT000", "CEPCT", "EKKO", "LFA1", "SKAT", "T001")

_storage_options: dict[str, str] | None = None


def get_storage_options() -> dict[str, str]:
    """The `storage_options` dict polars needs to read Delta tables from the
    lakehouse, built from `settings.AZURE_*` and cached after first build.
    """
    global _storage_options
    if _storage_options is None:
        missing = [
            name
            for name in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET")
            if not getattr(settings, name)
        ]
        if missing:
            raise ValueError(f"Missing lakehouse credentials in settings: {', '.join(missing)}")
        _storage_options = {
            "azure_tenant_id": settings.AZURE_TENANT_ID,
            "azure_client_id": settings.AZURE_CLIENT_ID,
            "azure_client_secret": settings.AZURE_CLIENT_SECRET,
            "use_fabric_endpoint": "true",
        }
    return _storage_options


def table_uri(table_name: str) -> str:
    """The Delta table URI for a SAP table name, e.g. `table_uri("BUT000")`."""
    if table_name not in AVAILABLE_TABLES:
        raise ValueError(f"Unknown lakehouse table '{table_name}'. Available tables: {', '.join(AVAILABLE_TABLES)}")
    if not settings.LAKEHOUSE_TABLES_PATH:
        raise ValueError("Missing LAKEHOUSE_TABLES_PATH in settings.")
    return f"{settings.LAKEHOUSE_TABLES_PATH.rstrip('/')}/{table_name}"


def scan_table(table_name: str) -> pl.LazyFrame:
    """A lazy scan of a SAP table, with filter/column pushdown available to callers."""
    return pl.scan_delta(table_uri(table_name), storage_options=get_storage_options())


def normalize_expr(column: str) -> pl.Expr:
    """Strips non-alphanumerics and uppercases a column, for matching VAT/PO
    codes whose formatting varies. Nulls stay null.
    """
    return pl.col(column).str.replace_all(r"[^A-Za-z0-9]", "").str.to_uppercase()


def strip_country_prefix(value: pl.Expr) -> pl.Expr:
    """Drops a leading two-letter country code from a normalized VAT.

    SAP stores nearly every VAT prefixed; a document often shows the number
    alone, which no exact match can reach.
    """
    return pl.when(value.str.contains(r"^[A-Z]{2}")).then(value.str.slice(2)).otherwise(value)


def strip_country_prefix_str(value: str) -> str:
    """`strip_country_prefix` for an already-normalized lookup value."""
    return value[2:] if len(value) > 2 and value[:2].isalpha() else value


class LakehouseRepository:
    """Base class for repositories over SAP tables replicated to the lakehouse.

    Subclass and set `__table_name__` (e.g. `BUT000`), same pattern as
    `api.sql.BaseRepository`. Add typed query methods on the subclass; the
    methods here are the generic primitives they build on.
    """

    __table_name__: str = ""

    def __init__(self, table: Optional[str] = None):
        self.table: str = table or self.__table_name__
        if not self.table:
            raise ValueError("Table name must be specified either via class attribute or constructor argument.")
        self.table = self.table.strip()

    def scan(self) -> pl.LazyFrame:
        return scan_table(self.table)

    def select(self, columns: Optional[list[str]] = None, **filters: Any) -> pl.DataFrame:
        """Rows matching equality `filters` (column=value), optionally projected
        to `columns`. No filters returns the whole table — use with care on
        large SAP tables.
        """
        lf = self.scan()
        for column, value in filters.items():
            lf = lf.filter(pl.col(column) == value)
        if columns is not None:
            lf = lf.select(columns)
        return lf.collect()

    def get_by(self, column: str, value: Any) -> Optional[dict[str, Any]]:
        """The first row where `column == value`, or None."""
        df = self.scan().filter(pl.col(column) == value).limit(1).collect()
        return df.row(0, named=True) if df.height > 0 else None

    def exists(self, column: str, value: Any) -> bool:
        """Whether any row has `column == value`."""
        return self.scan().filter(pl.col(column) == value).limit(1).collect().height > 0

    def rows_by_normalized(
        self,
        columns: Collection[str],
        value: str,
        projection: dict[str, pl.Expr],
        ignore_country_prefix: bool = False,
    ) -> list[dict[str, Any]]:
        """Every row whose `columns` coalesce to `value` once normalized,
        projected to `projection`'s aliases.

        `ignore_country_prefix` compares both sides without their leading
        country code, for a `value` read off a document that omitted it.

        A list because SAP holds one tax registration against several records —
        branches and vessels of one company share a VAT.
        """
        if not columns or not value:
            return []

        normalized = pl.coalesce([normalize_expr(column).replace("", None) for column in columns])
        if ignore_country_prefix:
            normalized = strip_country_prefix(normalized)
            value = strip_country_prefix_str(value)

        return self.scan().filter(normalized == value).select(**projection).collect().to_dicts()

    def known_normalized(
        self, columns: Collection[str], values: Collection[str], ignore_country_prefix: bool = False
    ) -> set[str]:
        """Which already-normalized `values` the table holds, in one scan.

        `columns` in precedence order: each is normalized and blanked to null,
        then the first non-null is the row's value. A supplier's VAT is STCEG
        (EU registration), or STCD1 (domestic id) where STCEG is empty.

        `ignore_country_prefix` compares both sides without their leading
        country code, and returns the values in that same bare form.
        """
        if not columns or not values:
            return set()

        normalized = pl.coalesce([normalize_expr(column).replace("", None) for column in columns])
        if ignore_country_prefix:
            normalized = strip_country_prefix(normalized)
            values = [strip_country_prefix_str(value) for value in values]

        df = self.scan().select(normalized.alias("value")).filter(pl.col("value").is_in(values)).unique().collect()
        return set(df.get_column("value").to_list())
