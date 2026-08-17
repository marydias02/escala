"""Small async Postgres helpers over asyncpg — the project's DB-write entry point.

This is deliberately thin and generic: parameterized INSERT / SELECT built from
plain dicts, so callers do not hand-write SQL and a future move to a repository
layer touches one place. It reuses the application's own connection pool
(`api.sql._default_pool`, created by `init_database_pool`), so the same code works
inside the FastAPI app and from a standalone `asyncio.run(...)` script.

JSONB and array columns:
- pass a JSONB value as a Python dict/list under a key named in `jsonb_columns`;
  it is `json.dumps`-ed and cast with `$n::jsonb` (no asyncpg codec needed).
- pass a TEXT[]/array column as a native Python list; asyncpg maps it directly.
"""

import json
from typing import Any, Iterable, Optional

import asyncpg

import api.sql as _sql


async def get_pool() -> asyncpg.Pool:
    """The shared asyncpg pool, initializing it on first use.

    In the FastAPI app the pool is created by the lifespan; a standalone script
    has no lifespan, so we lazily initialize it here.
    """
    pool = _sql._default_pool
    if pool is None or pool.is_closing():
        await _sql.init_database_pool()
        pool = _sql._default_pool
    assert pool is not None  # init_database_pool populates the global
    return pool


def _placeholder(index: int, column: str, jsonb_columns: Iterable[str]) -> str:
    """`$n`, or `$n::jsonb` for JSONB columns so a json string casts cleanly."""
    return f"${index}::jsonb" if column in jsonb_columns else f"${index}"


def _encode(column: str, value: Any, jsonb_columns: Iterable[str]) -> Any:
    """Serialize JSONB values to a json string; pass everything else through."""
    if column in jsonb_columns and value is not None:
        return json.dumps(value, ensure_ascii=False)
    return value


async def insert_row(
    table: str,
    values: dict[str, Any],
    *,
    returning: Optional[str] = None,
    jsonb_columns: Iterable[str] = (),
) -> Any:
    """Insert one row from a {column: value} dict.

    Only the columns present in `values` are written, so DB-side defaults
    (`gen_random_uuid()`, `now()`, ...) fill the rest — do not pass those keys.
    Returns the `returning` column's value (e.g. a generated id), or None.
    """
    columns = list(values.keys())
    placeholders = ", ".join(_placeholder(i, col, jsonb_columns) for i, col in enumerate(columns, start=1))
    params = [_encode(col, values[col], jsonb_columns) for col in columns]

    query = f'INSERT INTO {table} ({", ".join(columns)}) VALUES ({placeholders})'
    if returning:
        query += f" RETURNING {returning}"

    pool = await get_pool()
    if returning:
        return await pool.fetchval(query, *params)
    await pool.execute(query, *params)
    return None


async def insert_rows(
    table: str,
    rows: list[dict[str, Any]],
    *,
    jsonb_columns: Iterable[str] = (),
) -> int:
    """Insert several rows in one transaction. Returns the number of rows written.

    Every row must have the same column set (they share one prepared statement).
    Rows may omit columns to accept DB-side defaults, as with `insert_row`.
    """
    if not rows:
        return 0

    columns = list(rows[0].keys())
    placeholders = ", ".join(_placeholder(i, col, jsonb_columns) for i, col in enumerate(columns, start=1))
    query = f'INSERT INTO {table} ({", ".join(columns)}) VALUES ({placeholders})'

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            for row in rows:
                params = [_encode(col, row[col], jsonb_columns) for col in columns]
                await conn.execute(query, *params)
    return len(rows)


async def select(query: str, params: Optional[Iterable[Any]] = None) -> list[dict[str, Any]]:
    """Run a SELECT and return the rows as a list of dicts."""
    pool = await get_pool()
    records = await pool.fetch(query, *(params or []))
    return [dict(record) for record in records]


async def update_column(table: str, id_column: str, row_id: Any, column: str, value: Any) -> None:
    """Set one column on one row, matched by its id. `UPDATE table SET column = value WHERE id_column = row_id`."""
    pool = await get_pool()
    await pool.execute(f"UPDATE {table} SET {column} = $1 WHERE {id_column} = $2", value, row_id)
