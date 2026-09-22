"""Ranked entity search over the SAP dimension and fact snapshots.

Every normalized form compared here (`id_norm`, `vat_norm`, `vat_core`,
`name_norm`) is a STORED generated column from migration 20260918_02, so no
expression is recomputed per row and each comparison can use its own index.
The query side is normalized by the same `public.f_search_norm` the columns
were built with, so the two can never drift.

LIKE patterns need no escaping: every value reaching a LIKE has already been
reduced to `[A-Za-z0-9 ]` by `normalize_key` (service side) or `f_search_norm`
(SQL side), so `%` and `_` cannot survive into a pattern.
"""

from typing import Any, Iterable

import polars as pl
from asyncpg import Record

from api.sql import BaseRepository

# `%` reads pg_trgm.similarity_threshold from the session, so every search pins
# it explicitly rather than inheriting the server default. `similarity() >= x`
# in WHERE would read the same but cannot use the GIN index.
TRIGRAM_SIMILARITY_THRESHOLD = 0.3

# Suppliers and business units differ only in table, id column and projection.
PARTY_SEARCH_SQL = """
WITH q AS (
    SELECT $2::text AS key,
           $3::text AS id_q,
           $4::text AS vat_core_q,
           public.f_search_norm($1::text) AS name_q
),
scored AS (
    SELECT {select},
           CASE
             WHEN e.id_norm = q.id_q                                                   THEN 100
             WHEN e.vat_norm = q.key                                                   THEN 95
             WHEN e.vat_core = q.vat_core_q                                            THEN 90
             WHEN e.id_norm LIKE q.id_q || '%'                                         THEN 80
             WHEN e.vat_norm LIKE q.key || '%' OR e.vat_core LIKE q.vat_core_q || '%'  THEN 75
             WHEN e.name_norm = q.name_q                                               THEN 70
             WHEN e.name_norm LIKE q.name_q || '%'                                     THEN 60
             WHEN e.name_norm LIKE '%' || q.name_q || '%'                              THEN 50
             WHEN e.name_norm % q.name_q                                               THEN 40
           END AS tier,
           similarity(e.name_norm, q.name_q) AS sim,
           length(e.name) AS name_length,
           e.{id} AS entity_id
    FROM {table} e CROSS JOIN q
    WHERE e.id_norm LIKE q.id_q || '%'
       OR e.vat_norm LIKE q.key || '%'
       OR e.vat_core LIKE q.vat_core_q || '%'
       OR e.name_norm LIKE '%' || q.name_q || '%'
       OR e.name_norm % q.name_q
)
SELECT {columns}
FROM scored
WHERE tier IS NOT NULL
ORDER BY tier DESC, sim DESC, name_length ASC, entity_id ASC
LIMIT $5
"""

# A NULL parameter disables its own branch: `= NULL` and `LIKE NULL` are both
# NULL, i.e. never true, so no IS NOT NULL guards are needed above.

PO_SEARCH_SQL = """
WITH q AS (
    SELECT $1::text AS code, $1::bigint AS code_num
),
exact_prefix AS (
    SELECT p.po_code, p.supplier_id, p.bu_id, p.date, p.value, p.currency,
           CASE WHEN p.po_code = q.code THEN 100 ELSE 80 END AS tier,
           1.0::real AS sim, 0::bigint AS distance
    FROM fct_purchase_orders p CROSS JOIN q
    WHERE p.po_code LIKE q.code || '%'
),
fuzzy AS (
    SELECT p.po_code, p.supplier_id, p.bu_id, p.date, p.value, p.currency,
           60 AS tier, similarity(p.po_code, q.code) AS sim, NULL::bigint AS distance
    FROM fct_purchase_orders p CROSS JOIN q
    WHERE length(q.code) >= 8 AND p.po_code % q.code
),
neighbours AS (
    (SELECT p.po_code, p.supplier_id, p.bu_id, p.date, p.value, p.currency
     FROM fct_purchase_orders p CROSS JOIN q
     WHERE length(q.code) = 10 AND p.po_code ~ '^[0-9]{10}$' AND p.po_code > q.code
     ORDER BY p.po_code ASC LIMIT $2)
    UNION ALL
    (SELECT p.po_code, p.supplier_id, p.bu_id, p.date, p.value, p.currency
     FROM fct_purchase_orders p CROSS JOIN q
     WHERE length(q.code) = 10 AND p.po_code ~ '^[0-9]{10}$' AND p.po_code < q.code
     ORDER BY p.po_code DESC LIMIT $2)
),
candidates AS (
    SELECT * FROM exact_prefix
    UNION ALL SELECT * FROM fuzzy
    UNION ALL
    SELECT n.po_code, n.supplier_id, n.bu_id, n.date, n.value, n.currency,
           40 AS tier, 0::real AS sim,
           abs(n.po_code::bigint - q.code_num)::bigint AS distance
    FROM neighbours n CROSS JOIN q
),
best AS (SELECT DISTINCT ON (po_code) * FROM candidates ORDER BY po_code, tier DESC)
SELECT b.po_code, b.supplier_id, b.bu_id, b.date, b.value, b.currency,
       s.name AS supplier_name, s.vat AS supplier_vat,
       u.name AS bu_name, u.vat AS bu_vat
FROM best b
LEFT JOIN dim_suppliers s ON s.supplier_id = b.supplier_id
LEFT JOIN dim_business_units u ON u.bu_id = b.bu_id
ORDER BY b.tier DESC, b.sim DESC, b.distance ASC NULLS LAST, b.date DESC NULLS LAST, b.po_code ASC
LIMIT $3
"""
# The joins are LEFT and sit only in the final SELECT: the dim tables are synced
# append-only with no FKs, so a PO can name a supplier the sync has not landed
# yet, and that must not drop the PO from results.


class _ThresholdSearchRepository(BaseRepository):
    """A repository whose queries use the pg_trgm `%` operator.

    `BaseRepository` runs everything on the pool with no transaction, but the
    trigram threshold has to be set on the same connection as the query and
    must not leak to the next borrower of that connection. `set_config(...,
    is_local => true)` inside a transaction gives exactly that scope.
    """

    async def _query_df_with_threshold(self, query: str, parameters: Iterable[Any]) -> pl.DataFrame:
        async with self.pool.acquire() as connection, connection.transaction():
            await connection.execute(
                "SELECT set_config('pg_trgm.similarity_threshold', $1, true)",
                str(TRIGRAM_SIMILARITY_THRESHOLD),
            )
            records: list[Record] = await connection.fetch(query, *parameters)
        if not records:
            return pl.DataFrame()
        columns = list(records[0].keys())
        return pl.DataFrame(data=(tuple(r) for r in records), schema=columns)


class _PartySearchRepository(_ThresholdSearchRepository):
    """Shared id/VAT/name ranking for the two party dimensions."""

    __id_column__: str = ""
    __columns__: tuple[str, ...] = ()

    @property
    def _sql(self) -> str:
        return PARTY_SEARCH_SQL.format(
            table=self.table,
            id=self.__id_column__,
            select=", ".join(f"e.{column}" for column in self.__columns__),
            columns=", ".join(self.__columns__),
        )

    async def search(
        self, raw: str, key: str | None, id_q: str | None, vat_core_q: str | None, limit: int
    ) -> pl.DataFrame:
        return await self._query_df_with_threshold(self._sql, [raw, key, id_q, vat_core_q, limit])


class SupplierSearchRepository(_PartySearchRepository):
    __table_name__ = "dim_suppliers"
    __id_column__ = "supplier_id"
    __columns__ = ("supplier_id", "name", "vat", "country", "is_financial")


class BusinessUnitSearchRepository(_PartySearchRepository):
    __table_name__ = "dim_business_units"
    __id_column__ = "bu_id"
    __columns__ = ("bu_id", "name", "vat", "country")


class PurchaseOrderSearchRepository(_ThresholdSearchRepository):
    __table_name__ = "fct_purchase_orders"

    async def search(self, code: str, limit: int) -> pl.DataFrame:
        """`code` must be 3..10 digits — the service guarantees it, and the
        `$1::bigint` cast in the query depends on it.
        """
        return await self._query_df_with_threshold(PO_SEARCH_SQL, [code, limit, limit])
