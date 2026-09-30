from api.sql import BaseRepository


class HarborRepository(BaseRepository):
    """Read models for the Harbor dashboard, ingestion and reconciliation pages."""

    __table_name__ = "fct_payments"

    async def query_dicts(self, query: str, parameters=None) -> list[dict]:
        return [dict(row) for row in await self.pool.fetch(query, *(parameters or []))]

    async def query_scalar_list(self, query: str, parameters=None) -> list:
        return [row[0] for row in await self.pool.fetch(query, *(parameters or []))]

    async def list_accounts(self) -> list[str]:
        query = f"SELECT DISTINCT account FROM {self.table} WHERE account IS NOT NULL ORDER BY account"
        return await self.query_scalar_list(query)

    async def list_payments(self, account: str | None = None, limit: int = 500) -> list[dict]:
        query = f"""
        SELECT
            payment_id AS trans_id,
            transfer_reference,
            account AS account_id,
            bu_id,
            date AS trans_date,
            description,
            value AS credit_debit,
            date AS proc_date,
            NULL::date AS val_date,
            CASE WHEN is_treasury THEN 'Tesouraria' ELSE 'Contas a Receber' END AS scope,
            is_treasury AS treasury,
            decision,
            status,
            currency,
            entry_type,
            source_bank_account,
            additional_info
        FROM {self.table}
        WHERE ($1::text IS NULL OR account = $1)
        ORDER BY date DESC, payment_id
        LIMIT $2
        """
        return await self.query_dicts(query, parameters=[account, limit])

    async def get_dashboard_indicators(self, account: str | None = None) -> dict:
        query = f"""
        SELECT
            COALESCE(SUM(value) FILTER (WHERE status IS NULL OR status NOT IN ('Finalizado', 'Fechado')), 0) AS amount_pending,
            COUNT(*) FILTER (WHERE status IS NULL OR status NOT IN ('Finalizado', 'Fechado')) AS movements_open,
            COUNT(*) FILTER (WHERE status = 'A aguardar NP') AS awaiting_payment_note,
            MAX(date) AS latest_transaction_date
        FROM {self.table}
        WHERE ($1::text IS NULL OR account = $1)
        """
        return await self.query_dict(query, parameters=[account])

    async def list_email_messages(self, limit: int = 500) -> list[dict]:
        query = """
        SELECT
            m.message_id,
            m.received_at,
            m.sender_email,
            m.subject,
            m.status,
            m.attempts,
            m.last_error,
            m.process_id,
            i.payment_information_id,
            i.is_payment_related,
            i.payment_note_code,
            i.extraction_content,
            i.body_pdf_path
        FROM payment_email_messages m
        LEFT JOIN payment_email_information i ON i.message_id = m.message_id
        ORDER BY m.received_at DESC NULLS LAST, m.message_id
        LIMIT $1
        """
        return await self.query_dicts(query, parameters=[limit])

    async def get_payment_reconciliation(self, payment_id: str) -> dict | None:
        payment = await self.query_dict(
            """
            SELECT payment_id AS trans_id, transfer_reference, account AS account_id, bu_id,
                   date AS trans_date, description, value AS credit_debit, currency,
                   source_bank_account, additional_info, entry_type, is_treasury AS treasury,
                   decision, status
            FROM fct_payments WHERE payment_id = $1
            """,
            parameters=[payment_id],
        )
        if not payment:
            return None

        notes = await self.query_dicts(
            """
            SELECT pn.payment_note_id, pn.payment_note_code, pn.document_number,
                   pn.value_paid, pn.currency, pn.path, pn.total_payment_note,
                   pn.status, pn.extracted_content
            FROM payment_analysis pa
            JOIN payment_notes pn ON pn.payment_note_id = pa.payment_note_id
            WHERE pa.payment_id = $1
            ORDER BY pn.payment_note_code NULLS LAST, pn.payment_note_id
            """,
            parameters=[payment_id],
        )
        matches = await self.query_dicts(
            """
            SELECT im.invoice_id, im.invoice_pending_value, im.matched_value,
                   im.final_pending_value, im.matched_currency,
                   i.billing_document AS document_number, i.issue_date AS posting_date,
                   i.document_nr AS document, i.total_amount AS net_amount,
                   im.matched_value AS paid_amount
            FROM invoice_matching im
            LEFT JOIN fct_invoices i ON i.invoice_id = im.invoice_id
            WHERE im.payment_id = $1
            ORDER BY i.billing_date NULLS LAST, im.invoice_id
            """,
            parameters=[payment_id],
        )
        analyses = await self.query_dicts(
            "SELECT payment_note_id, evidence, rationale FROM payment_analysis WHERE payment_id = $1",
            parameters=[payment_id],
        )
        return {"payment": payment, "payment_notes": notes, "allocations": matches, "analysis": analyses}

