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

from typing import Any, Optional

import polars as pl

from config.settings import settings

AVAILABLE_TABLES = ("ACDOCA", "BSAD", "BSEG", "BUT000", "CEPCT", "SKAT")

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
