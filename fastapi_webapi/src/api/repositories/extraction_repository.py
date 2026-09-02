from typing import Any, Optional

import polars as pl

from api.sql import BaseRepository
from invoice_extraction.decisions import EMAIL_STATUS_CLOSED, INGEST, MANUAL, REPLY

_DOCUMENT_LIST_COLUMNS = """
    document_id,
    document_content -> 'document_number' ->> 'value' AS document_number,
    document_content -> 'supplier_name' ->> 'value' AS supplier_name,
    document_content -> 'bu_name' ->> 'value' AS bu_name,
    (document_content -> 'total_amount' ->> 'value')::float AS total_amount,
    CASE
        WHEN document_content -> 'issue_date' ->> 'value' ~ '^\\d{2}-\\d{2}-\\d{4}$'
            THEN to_date(document_content -> 'issue_date' ->> 'value', 'DD-MM-YYYY')
        WHEN document_content -> 'issue_date' ->> 'value' ~ '^\\d{4}-\\d{2}-\\d{2}$'
            THEN (document_content -> 'issue_date' ->> 'value')::date
        ELSE NULL
    END AS issue_date,
    created_at,
    action,
    status
"""


class ExtractionBigNumbers(BaseRepository):
    __table_name__ = "fct_documents"

    async def count_pending_manual_validation(self) -> int:
        query = f"""
        SELECT COUNT(*) FROM {self.table}
        WHERE action = $1 AND status IN ('Criado', 'Sob Revisão')
        """
        return await self.query_scalar(query, parameters=[MANUAL])

    async def count_first_manual_by_week(self) -> dict[str, tuple[int, int]]:
        """Documents FIRST routed to manual validation, by the week they first
        landed there — from fct_document_first_action, which manual review
        never overwrites (unlike fct_documents.action).
        """
        query = """
        SELECT
            date_trunc('week', created_at) AS week,
            COUNT(*) FILTER (WHERE first_action = $1) AS matched,
            COUNT(*) AS total
        FROM fct_document_first_action
        WHERE date_trunc('week', created_at) IN (date_trunc('week', now()), date_trunc('week', now()) - interval '1 week')
        GROUP BY week
        """
        return await self._matched_and_total_by_week(query, parameters=[MANUAL])

    async def count_auto_ingested_by_week(self) -> dict[str, tuple[int, int]]:
        query = f"""
        SELECT
            date_trunc('week', created_at) AS week,
            COUNT(*) FILTER (
                WHERE action = $1 AND status = 'Ingerido' AND last_modified_by IS NULL
            ) AS matched,
            COUNT(*) AS total
        FROM {self.table}
        WHERE date_trunc('week', created_at) IN (date_trunc('week', now()), date_trunc('week', now()) - interval '1 week')
        GROUP BY week
        """
        return await self._matched_and_total_by_week(query, parameters=[INGEST])

    async def count_returned_to_supplier_by_week(self) -> dict[str, tuple[int, int]]:
        query = f"""
        SELECT
            date_trunc('week', created_at) AS week,
            COUNT(*) FILTER (WHERE action = $1) AS matched,
            COUNT(*) AS total
        FROM {self.table}
        WHERE date_trunc('week', created_at) IN (date_trunc('week', now()), date_trunc('week', now()) - interval '1 week')
        GROUP BY week
        """
        return await self._matched_and_total_by_week(query, parameters=[REPLY])

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


class BusinessUnitRepository(BaseRepository):
    __table_name__ = "dim_business_units"

    async def exists_by_vat(self, vat: str) -> bool:
        query = f"SELECT EXISTS(SELECT 1 FROM {self.table} WHERE vat = $1)"
        return await self.query_scalar(query, parameters=[vat])


class ProcessesRepository(BaseRepository):
    __table_name__ = "fct_processes"

    async def close(self, process_id) -> bool:
        """Mark a process `Fechado`. False if it was already closed."""
        query = f"""
        UPDATE {self.table}
        SET email_status = $2
        WHERE process_id = $1 AND email_status IS DISTINCT FROM $2
        RETURNING process_id
        """
        updated = await self.query_scalar(query, parameters=[process_id, EMAIL_STATUS_CLOSED])
        return updated is not None


class DocumentsRepository(BaseRepository):
    __table_name__ = "fct_documents"

    async def list_priority_documents(self, limit: int = 100) -> pl.DataFrame:
        query = f"""
        SELECT {_DOCUMENT_LIST_COLUMNS}
        FROM {self.table}
        WHERE action = $1 AND status IN ('Criado', 'Sob Revisão') 
            AND document_content <> '{{}}'::jsonb
        ORDER BY created_at ASC, document_id DESC
        LIMIT $2
        """
        return await self.query_df(query, parameters=[MANUAL, limit])

    async def get_next_priority_document(self, document_id: str) -> Optional[dict]:
        query = f"""
        WITH current_document AS (
            SELECT
                created_at,
                action = $2
                    AND status IN ('Criado', 'Sob Revisão') 
                    AND document_content <> '{{}}'::jsonb AS eligible
            FROM {self.table}
            WHERE document_id = $1
        )
        SELECT
            current_document.eligible,
            (
                SELECT candidate.document_id
                FROM {self.table} AS candidate
                WHERE current_document.eligible
                    AND candidate.action = $2
                    AND candidate.status = 'Criado'
                    AND (candidate.created_at, candidate.document_id)
                        > (current_document.created_at, $1)
                ORDER BY candidate.created_at ASC, candidate.document_id DESC
                LIMIT 1
            ) AS next_document_id
        FROM current_document
        """
        return await self.query_dict(query, parameters=[document_id, MANUAL])

    async def list_all_documents(self, limit: int = 100) -> pl.DataFrame:
        query = f"""
        SELECT {_DOCUMENT_LIST_COLUMNS}
        FROM {self.table}
        WHERE status <> 'Ignorado'
            AND document_content <> '{{}}'::jsonb
        ORDER BY created_at DESC
        LIMIT $1
        """
        return await self.query_df(query, parameters=[limit])

    async def list_pending_documents(self, limit: int = 100) -> pl.DataFrame:
        query = f"""
        SELECT
            {_DOCUMENT_LIST_COLUMNS},
            p.sender_email,
            p.email_subject
        FROM {self.table} d
        LEFT JOIN fct_processes p ON p.process_id = d.process_id
        WHERE d.status IN ('Ignorado', 'Criado')
            AND d.document_content = '{{}}'::jsonb
        ORDER BY created_at DESC
        LIMIT $1
        """
        return await self.query_df(query, parameters=[limit])

    async def get_document(self, document_id: str) -> Optional[dict]:
        query = f"""
        SELECT document_id, alerts_list, document_content, document_type, action, status
        FROM {self.table}
        WHERE document_id = $1
        """
        return await self.query_dict(query, parameters=[document_id])

    async def list_process_document_states(self, process_id) -> list[tuple[Optional[str], Optional[str]]]:
        """(action, status) for each of a process's documents."""
        query = f"SELECT action, status FROM {self.table} WHERE process_id = $1"
        df = await self.query_df(query, parameters=[process_id])
        if df.is_empty():
            return []
        return [(row["action"], row["status"]) for row in df.iter_rows(named=True)]

    async def set_status(self, document_id: str, status: str) -> None:
        query = f"UPDATE {self.table} SET status = $2 WHERE document_id = $1"
        await self.execute(query, parameters=[document_id, status])

    async def get_document_email(self, document_id: str) -> Optional[dict]:
        query = f"""
        SELECT p.sender_email, p.email_subject, p.email_content, p.reception_date
        FROM {self.table} d
        JOIN fct_processes p ON p.process_id = d.process_id
        WHERE d.document_id = $1
        """
        return await self.query_dict(query, parameters=[document_id])

    async def get_process_id(self, document_id: str) -> Optional[str]:
        query = f"SELECT process_id FROM {self.table} WHERE document_id = $1"
        return await self.query_scalar(query, parameters=[document_id])

    async def get_file_path(self, document_id: str) -> Optional[str]:
        query = f"SELECT file_path FROM {self.table} WHERE document_id = $1"
        return await self.query_scalar(query, parameters=[document_id])
    
    async def alter(self, data: dict) -> dict[str, Any]:
        query = f"""
        UPDATE {self.table}
        SET alerts_list = $2, document_content = $3, action = $4, status = $5, last_modified_by = $6, last_modified_at = now()
        WHERE document_id = $1
        RETURNING document_id, alerts_list, document_content, action, status, last_modified_by, last_modified_at;
        """
        params = [data["document_id"], data["alerts_list"], data["document_content"], data["action"], data["status"], data["last_modified_by"]]

        return await self.query_dict(query, parameters=params)
