import polars as pl

from api.sql import BaseRepository

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
