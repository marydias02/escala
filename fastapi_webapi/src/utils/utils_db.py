"""Small async Postgres helpers over asyncpg — the project's DB-write entry point.

This is deliberately thin and generic: parameterized INSERT / SELECT built from
plain dicts, so callers do not hand-write SQL and a future move to a repository
layer touches one place. It reuses the application's own connection pool
(`api.sql._default_pool`, created by `init_database_pool`), so the same code works
inside the FastAPI app and from a standalone `asyncio.run(...)` script.

`select_sync` is the one exception to the async interface — see the sync bridge
below for why the validation tools need it.

JSONB and array columns:
- pass a JSONB value as a Python dict/list under a key named in `jsonb_columns`;
  it is `json.dumps`-ed and cast with `$n::jsonb` (no asyncpg codec needed).
- pass a TEXT[]/array column as a native Python list; asyncpg maps it directly.
"""

import asyncio
import json
import threading
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


# --- sync bridge -------------------------------------------------------------
# The `@tool` functions in invoice_extraction.tools are sync, but already run on
# the event loop thread — `asyncio.run(...)` there raises "This event loop is
# already running". So the query goes to a background loop instead and the caller
# blocks on the result. That loop needs its own pool, since an asyncpg pool only
# works on the loop that created it.

_bridge_loop: Optional[asyncio.AbstractEventLoop] = None
_bridge_pool: Optional[asyncpg.Pool] = None
_bridge_lock = threading.Lock()


def _bridge() -> asyncio.AbstractEventLoop:
    """The background loop, started on first use as a daemon thread."""
    global _bridge_loop
    with _bridge_lock:
        if _bridge_loop is None or _bridge_loop.is_closed():
            _bridge_loop = asyncio.new_event_loop()
            threading.Thread(
                target=_bridge_loop.run_forever, name="utils-db-bridge", daemon=True
            ).start()
        return _bridge_loop


async def _bridge_get_pool() -> asyncpg.Pool:
    """The bridge's own pool. `init_database_pool` returns the pool it builds and
    only claims `_default_pool` when unset, so this borrows the DSN without
    stealing the app's pool.
    """
    global _bridge_pool
    if _bridge_pool is None or _bridge_pool.is_closing():
        _bridge_pool = await _sql.init_database_pool()
    return _bridge_pool


def select_sync(
    query: str, params: Optional[Iterable[Any]] = None, timeout: float = 10.0
) -> list[dict[str, Any]]:
    """`select()` for synchronous callers. Runs on the background loop and blocks.

    Raises whatever the query raises, or `TimeoutError` past `timeout`.
    """

    async def _run() -> list[dict[str, Any]]:
        pool = await _bridge_get_pool()
        records = await pool.fetch(query, *(params or []))
        return [dict(record) for record in records]

    return asyncio.run_coroutine_threadsafe(_run(), _bridge()).result(timeout=timeout)


def normalize_key(value: Optional[str]) -> Optional[str]:
    """Strip non-alphanumerics and uppercase, for matching VAT/PO codes whose
    formatting varies between SAP and the document (`PT 501 925 350` vs
    `PT501925350`). `normalize_sql` is the column-side equivalent.

    Country prefixes are kept: `PT501925350` and `501925350` stay distinct.
    """
    if not value:
        return None
    return "".join(char for char in value if char.isalnum()).upper() or None


def normalize_sql(column: str) -> str:
    """`normalize_key` as SQL, so a stored value matches a normalized parameter."""
    return f"upper(regexp_replace({column}, '[^A-Za-z0-9]', '', 'g'))"


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
    chunk_size: int = 1000,
) -> int:
    """Insert several rows, one transaction per `chunk_size`-row batch. Returns the
    number of rows written.

    Every row must have the same column set (they share one prepared statement).
    Rows may omit columns to accept DB-side defaults, as with `insert_row`.

    Chunked rather than one big transaction so a large load (tens of thousands of
    rows) does not hold a single lock/transaction open for its whole duration --
    that starves other queries on `table` and leaves a lock behind for however
    long it takes if the caller is interrupted mid-run.
    """
    if not rows:
        return 0

    columns = list(rows[0].keys())
    placeholders = ", ".join(_placeholder(i, col, jsonb_columns) for i, col in enumerate(columns, start=1))
    query = f'INSERT INTO {table} ({", ".join(columns)}) VALUES ({placeholders})'

    pool = await get_pool()
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        chunk_params = [[_encode(col, row[col], jsonb_columns) for col in columns] for row in chunk]
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(query, chunk_params)
    return len(rows)


async def upsert_rows(
    table: str,
    rows: list[dict[str, Any]],
    *,
    conflict_columns: Iterable[str],
    update_columns: Optional[Iterable[str]] = None,
    jsonb_columns: Iterable[str] = (),
    chunk_size: int = 1000,
) -> int:
    """`insert_rows` with ON CONFLICT DO UPDATE. Returns the rows sent.

    `update_columns` defaults to every column except the conflict ones; an empty
    one degrades to DO NOTHING.

    Never pass a GENERATED ALWAYS column (dim_suppliers/dim_business_units have
    four, see the 20260918_02 migration) in `rows` or `update_columns` — Postgres
    rejects the write. It recomputes them on UPDATE by itself.
    """
    if not rows:
        return 0

    columns = list(rows[0].keys())
    conflict = list(conflict_columns)
    updates = list(update_columns) if update_columns is not None else [c for c in columns if c not in conflict]

    placeholders = ", ".join(_placeholder(i, col, jsonb_columns) for i, col in enumerate(columns, start=1))
    action = "DO UPDATE SET " + ", ".join(f"{col} = EXCLUDED.{col}" for col in updates) if updates else "DO NOTHING"
    query = (
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT ({', '.join(conflict)}) {action}"
    )

    pool = await get_pool()
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        chunk_params = [[_encode(col, row[col], jsonb_columns) for col in columns] for row in chunk]
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(query, chunk_params)
    return len(rows)


async def delete_rows(table: str, key_column: str, keys: list[Any], *, chunk_size: int = 1000) -> int:
    """Delete rows whose `key_column` is in `keys`. Returns the number deleted."""
    if not keys:
        return 0

    query = f"DELETE FROM {table} WHERE {key_column} = ANY($1)"
    pool = await get_pool()
    deleted = 0
    for start in range(0, len(keys), chunk_size):
        tag = await pool.execute(query, keys[start : start + chunk_size])
        # asyncpg returns the command tag, e.g. "DELETE 12".
        deleted += int(tag.rsplit(" ", 1)[-1])
    return deleted


async def select(query: str, params: Optional[Iterable[Any]] = None) -> list[dict[str, Any]]:
    """Run a SELECT and return the rows as a list of dicts."""
    pool = await get_pool()
    records = await pool.fetch(query, *(params or []))
    return [dict(record) for record in records]


async def update_column(table: str, id_column: str, row_id: Any, column: str, value: Any) -> None:
    """Set one column on one row, matched by its id. `UPDATE table SET column = value WHERE id_column = row_id`."""
    pool = await get_pool()
    await pool.execute(f"UPDATE {table} SET {column} = $1 WHERE {id_column} = $2", value, row_id)
