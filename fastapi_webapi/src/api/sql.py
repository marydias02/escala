from typing import Any, Iterable

import asyncpg
import polars as pl
from asyncpg import Record

from api.properties import DATABASE_URI

_default_pool: asyncpg.Pool | None = None


async def init_database_pool(uri=DATABASE_URI) -> asyncpg.Pool:
    global _default_pool
    new_pool = await asyncpg.create_pool(dsn=uri, min_size=2, max_size=10)
    if _default_pool is None or _default_pool.is_closing():
        _default_pool = new_pool
    return new_pool


def get_database_pool() -> asyncpg.Pool | None:
    """The pool `init_database_pool` created, or None before the lifespan runs."""
    return _default_pool


class BaseRepository:
    __table_name__: str = ""

    def __init__(self, schema: str = "public", table: str | None = None, pool: asyncpg.Pool | None = None):
        if pool is None:
            if _default_pool is None or _default_pool.is_closing():
                raise ValueError("Default pool is not initialized. Please provide a connection pool.")
            self.pool = _default_pool
        else:
            self.pool = pool
        self.schema = schema.strip()
        self.table: str = table or self.__table_name__
        if not self.table:
            raise ValueError("Table name must be specified either via class attribute or constructor argument.")
        self.table = self.table.strip()

    async def execute(self, query: str, parameters: Iterable[Any] | None = None) -> str:
        return await self.pool.execute(query, *(parameters or []))

    async def query_scalar(self, query: str, parameters: Iterable[Any] | None = None) -> Any:
        return await self.pool.fetchval(query, *(parameters or []))

    async def query_tuple(self, query: str, parameters: Iterable[Any] | None = None) -> dict[str, Any]:
        record = await self.pool.fetchrow(query, *(parameters or []))
        return tuple(record) if record is not None else {}

    async def query_dict(self, query: str, parameters: Iterable[Any] | None = None) -> dict[str, Any]:
        record = await self.pool.fetchrow(query, *(parameters or []))
        return dict(record) if record is not None else {}

    async def query_df(self, query: str, parameters: Iterable[Any] | None = None) -> pl.DataFrame:
        records: list[Record] = await self.pool.fetch(query, *(parameters or []))
        if not records:
            return pl.DataFrame()
        columns = list(records[0].keys())
        rows = (tuple(r) for r in records)
        return pl.DataFrame(data=rows, schema=columns)

    async def upload_df(self, df: pl.DataFrame) -> int:
        if df.is_empty():
            return 0
        columns: list[str] = df.collect_schema().names()
        status: str | None = await self.pool.copy_records_to_table(
            self.table,
            records=(tuple(r) for r in df.select(columns).iter_rows()),
            columns=columns,
            schema_name=self.schema,
        )
        return int((status or "COUNT 0").split()[-1])

    async def list_tables(self) -> list[str]:
        df = await self.query_df(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = $1", parameters=[self.schema]
        )
        return df["table_name"].to_list() if not df.is_empty() else []
