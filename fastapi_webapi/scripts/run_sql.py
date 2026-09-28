"""Run arbitrary SQL against the app database (DATABASE_URI) from the console.

    python scripts/run_sql.py "SELECT * FROM webapp.sessions LIMIT 10"
    python scripts/run_sql.py -f query.sql
    python scripts/run_sql.py "SELECT ..." --csv out.csv       # also write all rows to a CSV
    python scripts/run_sql.py "SELECT ..." --width 0           # don't truncate cells
    python scripts/run_sql.py                                  # interactive prompt, end statements with ';'

Every query first runs inside a READ ONLY transaction. If Postgres rejects it for
writing (INSERT/UPDATE/DELETE/DROP/TRUNCATE/ALTER/...), it is rolled back and
you are asked to confirm (y/n) before it runs for real in a normal transaction.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import asyncpg

from api.properties import DATABASE_URI

MAX_CELL_WIDTH = 60
DEFAULT_ROW_LIMIT = 200


class _Result:
    def __init__(self, columns: list[str], rows: list[tuple], status: str):
        self.columns = columns
        self.rows = rows
        self.status = status


async def _fetch(conn: asyncpg.Connection, sql: str) -> _Result:
    try:
        # Savepoint so a failed prepare doesn't abort the outer transaction.
        async with conn.transaction():
            stmt = await conn.prepare(sql)
    except asyncpg.PostgresSyntaxError as exc:
        # Multiple statements can't be prepared; run them as a script without results.
        if "multiple commands" not in str(exc):
            raise
        return _Result([], [], await conn.execute(sql))
    rows = [tuple(r) for r in await stmt.fetch()]
    columns = [a.name for a in stmt.get_attributes()]
    return _Result(columns, rows, stmt.get_statusmsg())


def _confirm(reason: str) -> bool:
    try:
        answer = input(f"{reason}\nProceed? (y/n) ").strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


async def run_query(conn: asyncpg.Connection, sql: str) -> _Result | None:
    in_transaction = True
    try:
        async with conn.transaction(readonly=True):
            return await _fetch(conn, sql)
    except asyncpg.ReadOnlySQLTransactionError:
        reason = "This query modifies the database."
    except asyncpg.ActiveSQLTransactionError:
        # E.g. VACUUM, CREATE INDEX CONCURRENTLY: can't run inside a transaction.
        reason = "This query modifies the database and cannot be rolled back."
        in_transaction = False

    if not _confirm(reason):
        print("Aborted.")
        return None
    if not in_transaction:
        return await _fetch(conn, sql)
    async with conn.transaction():
        return await _fetch(conn, sql)


def _fmt(value: Any, width: int) -> str:
    if value is None:
        return "NULL"
    text = str(value).replace("\r", "").replace("\n", "\\n")
    return text if width <= 0 or len(text) <= width else text[: width - 3] + "..."


def print_result(result: _Result, limit: int, width: int) -> None:
    if result.columns:
        shown = [[_fmt(v, width) for v in row] for row in result.rows[:limit]]
        widths = [max([len(c)] + [len(r[i]) for r in shown]) for i, c in enumerate(result.columns)]
        print(" | ".join(c.ljust(w) for c, w in zip(result.columns, widths)))
        print("-+-".join("-" * w for w in widths))
        for row in shown:
            print(" | ".join(v.ljust(w) for v, w in zip(row, widths)))
        suffix = f", showing first {limit}" if len(result.rows) > limit else ""
        print(f"({len(result.rows)} row(s){suffix})")
    print(result.status)


def write_csv(result: _Result, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(result.columns)
        writer.writerows(result.rows)
    print(f"Wrote {len(result.rows)} row(s) to {path}")


async def _execute_and_print(conn: asyncpg.Connection, sql: str, args: argparse.Namespace) -> None:
    try:
        result = await run_query(conn, sql)
    except asyncpg.PostgresError as exc:
        print(f"ERROR: {exc.__class__.__name__}: {exc}")
        return
    if result is None:
        return
    print_result(result, args.limit, args.width)
    if args.csv and result.columns:
        write_csv(result, args.csv)


async def _repl(conn: asyncpg.Connection, args: argparse.Namespace) -> None:
    print("Enter SQL ending with ';'. Type \\q to quit.")
    buffer: list[str] = []
    while True:
        try:
            line = input("...> " if buffer else "sql> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not buffer and line.strip() in ("\\q", "quit", "exit"):
            return
        buffer.append(line)
        if line.rstrip().endswith(";"):
            sql = "\n".join(buffer).strip()
            buffer.clear()
            await _execute_and_print(conn, sql, args)


async def main_async(args: argparse.Namespace) -> None:
    sql = args.file.read_text(encoding="utf-8") if args.file else args.query
    conn = await asyncpg.connect(DATABASE_URI)
    try:
        if sql:
            await _execute_and_print(conn, sql.strip(), args)
        else:
            await _repl(conn, args)
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SQL against the app database.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("query", nargs="?", help="SQL to run; omit for an interactive prompt")
    source.add_argument("-f", "--file", type=Path, help="read SQL from a file")
    parser.add_argument("--csv", type=Path, help="also write the result rows to this CSV file")
    parser.add_argument("--limit", type=int, default=DEFAULT_ROW_LIMIT, help="max rows printed to the console")
    parser.add_argument("--width", type=int, default=MAX_CELL_WIDTH, help="max cell width; 0 disables truncation")
    asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    main()
