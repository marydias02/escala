"""Delete expired rows from webapp.sessions.

    python scripts/sweep_sessions.py

Why this exists
---------------
`webapp.sessions` (see migration 20260908_01) only ever shrinks when the Dash
frontend explicitly deletes a row on sign-out. Every other ending — a closed
tab, a cookie that expired overnight, a browser that simply forgot — leaves the
row behind with an `expires_at` in the past. Nothing reads those rows again (the
frontend's SessionInterface treats `expires_at < now()` as "no session"), but
they accumulate without bound, bloating the table and its `expires_at` index.

This is housekeeping, not correctness: the app is right without it, it just
leaks storage. Run it on whatever schedule this ends up being deployed with; a
one-shot script rather than a background thread precisely so that choice stays
open. The `expires_at` index keeps it an index scan, not a full-table scan.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import asyncpg
from loguru import logger

from api.properties import DATABASE_URI


async def _sweep() -> int:
    conn = await asyncpg.connect(DATABASE_URI)
    try:
        tag = await conn.execute("DELETE FROM webapp.sessions WHERE expires_at < now()")
    finally:
        await conn.close()
    # asyncpg returns the command tag, e.g. "DELETE 42".
    return int(tag.split()[-1])


def main() -> None:
    deleted = asyncio.run(_sweep())
    logger.info(f"Swept {deleted} expired session row(s) from webapp.sessions")


if __name__ == "__main__":
    main()
