"""Repositories backing the validation dashboard: `sap_processes` reads for the
document list and the big-numbers tiles.
"""

import polars as pl

from api.sql import BaseRepository
from non_conformities_resolution.resolution_rules import (
    STATUS_AUTO,
    STATUS_BY_AGENT,
    STATUS_NEEDS_MANUAL,
    STATUS_WITH_BUYER,
)

_VALIDATION_DOCUMENT_LIST_COLUMNS = """
    p.reference_no,
    s.name AS supplier_name,
    bu.name AS bu_name,
    p.doc_id,
    p.total_amount,
    p.document_date,
    p.is_financial,
    p.last_interaction,
    p.last_interaction_datetime,
    p.status,
    p.issue,
    p."owner",
    p.reconciled
"""


class DocumentsRepository(BaseRepository):
    __table_name__ = "sap_processes"

    async def list_all_documents(self, limit: int = 100) -> pl.DataFrame:
        query = f"""
        SELECT {_VALIDATION_DOCUMENT_LIST_COLUMNS}
        FROM {self.table} p
        LEFT JOIN dim_suppliers s ON s.supplier_id = p.supplier_id
        LEFT JOIN dim_business_units bu ON bu.bu_id = p.bu_id
        ORDER BY p.last_interaction_datetime DESC NULLS LAST, p.document_date DESC NULLS LAST, p.reference_no
        LIMIT $1
        """
        return await self.query_df(query, parameters=[limit])


class ValidationBigNumbers(BaseRepository):
    """Weekly tile counts for the validation dashboard, bucketed by
    `added_in_sap_timestamp` — when SAP created the process, not when we last
    interacted with it.
    """

    __table_name__ = "sap_processes"

    async def count_non_conforming_received_by_week(self) -> dict[str, tuple[int, int]]:
        """Non-conforming processes received, excluding STATUS_AUTO (fully
        automatic processing never surfaces as a non-conformity to validate).
        """
        query = f"""
        SELECT
            date_trunc('week', added_in_sap_timestamp) AS week,
            COUNT(*) FILTER (WHERE status <> $1 OR status IS NULL) AS matched,
            COUNT(*) AS total
        FROM {self.table}
        WHERE date_trunc('week', added_in_sap_timestamp)
            IN (date_trunc('week', now()), date_trunc('week', now()) - interval '1 week')
        GROUP BY week
        """
        return await self._matched_and_total_by_week(query, parameters=[STATUS_AUTO])

    async def count_needs_manual_validation_by_week(self) -> dict[str, tuple[int, int]]:
        return await self._count_by_status_by_week(STATUS_NEEDS_MANUAL)

    async def count_processed_by_agent_by_week(self) -> dict[str, tuple[int, int]]:
        return await self._count_by_status_by_week(STATUS_BY_AGENT)

    async def count_with_buyer_by_week(self) -> dict[str, tuple[int, int]]:
        return await self._count_by_status_by_week(STATUS_WITH_BUYER)

    async def _count_by_status_by_week(self, status: str) -> dict[str, tuple[int, int]]:
        query = f"""
        SELECT
            date_trunc('week', added_in_sap_timestamp) AS week,
            COUNT(*) FILTER (WHERE status = $1) AS matched,
            COUNT(*) AS total
        FROM {self.table}
        WHERE date_trunc('week', added_in_sap_timestamp)
            IN (date_trunc('week', now()), date_trunc('week', now()) - interval '1 week')
        GROUP BY week
        """
        return await self._matched_and_total_by_week(query, parameters=[status])

    async def _matched_and_total_by_week(self, query: str, parameters: list) -> dict[str, tuple[int, int]]:
        df = await self.query_df(query, parameters=parameters)
        result: dict[str, tuple[int, int]] = {"current": (0, 0), "previous": (0, 0)}
        if df.is_empty():
            return result
        current_week = df["week"].max()
        for row in df.iter_rows(named=True):
            key = "current" if row["week"] == current_week else "previous"
            result[key] = (row["matched"], row["total"])
        return result
