"""SAP tables -> dim_/fct_ rows. Pure polars, no I/O."""

from __future__ import annotations

import polars as pl

from lakehouse_etl.config import (
    BOTH_SUPPLIERS,
    CREDIT_MEMO_POSTING_KEYS,
    FINANCIAL_SUPPLIERS,
    INVOICE_POSTING_KEY,
    PO_HELD_FLAG,
    REPOSTED_RECEIVABLE_INDICATOR,
    REPOSTED_RECEIVABLE_POSTING_KEY,
)
from utils.lakehouse_tables_column_mappings import SAPTableMetadata

# Columns written to each table. The generated columns (id_norm, vat_norm,
# vat_core, name_norm) are deliberately absent — Postgres rejects writes to them.
SUPPLIER_COLUMNS = ("supplier_id", "name", "vat", "country", "preferred_language", "is_financial")
BUSINESS_UNIT_COLUMNS = ("bu_id", "name", "vat", "country")
PURCHASE_ORDER_COLUMNS = ("po_code", "supplier_id", "bu_id", "date", "value", "currency", "source_changed_at")
CLIENT_COLUMNS = ("client_id", "name", "vat")
INVOICE_COLUMNS = (
    "invoice_id",
    "bu_id",
    "fiscal_year",
    "document_nr",
    "line",
    "client_id",
    "document_type",
    "billing_document",
    "original_document_nr",
    "issue_date",
    "due_date",
    "total_amount",
    "amount_paid",
    "amount_credited",
    "open_amount",
    "currency",
)

# `utils.sap_queries` returns readable column names; these map SAP names to
# them, so the transforms below still read in SAP's vocabulary.
_BUT000 = SAPTableMetadata(table_name="BUT000").readable_column_names
_BSEG = SAPTableMetadata(table_name="BSEG").readable_column_names

# Same precision as BSEG.WRBTR.
_AMOUNT = pl.Decimal(23, 2)


def full_name() -> pl.Expr:
    """Join LFA1/KNA1 NAME1-NAME4; SAP splits long names across the 35-char lines."""
    lines = []
    for col in ("NAME1", "NAME2", "NAME3", "NAME4"):
        trimmed = pl.col(col).cast(pl.String).str.strip_chars()
        # Blank dot-only placeholder lines (one supplier uses "." to fill NAME3/NAME4)
        lines.append(pl.when(trimmed.str.contains(r"^\.+$")).then(None).otherwise(trimmed))
    return (
        pl.concat_str(lines, separator=" ", ignore_nulls=True)
        .str.replace_all(r"\s+", " ")
        .str.strip_chars()
        .alias("name")
    )


def classify_is_financial() -> pl.Expr:
    """0 = logistics, 1 = financial, 2 = both. Matched on the display name."""
    return (
        pl.when(pl.col("name").is_in(BOTH_SUPPLIERS))
        .then(2)
        .when(pl.col("name").is_in(FINANCIAL_SUPPLIERS))
        .then(1)
        .otherwise(0)
        .alias("is_financial")
    )


def unmatched_financial_names(suppliers: pl.DataFrame) -> list[str]:
    """Listed names that matched no supplier. The lists key on a display name
    SAP can edit, so drift is silent without this.
    """
    known = set(suppliers.get_column("name").to_list())
    return sorted(name for name in [*FINANCIAL_SUPPLIERS, *BOTH_SUPPLIERS] if name not in known)


def build_suppliers(lfa1: pl.DataFrame, but000: pl.DataFrame) -> pl.DataFrame:
    """LFA1 (+ BUT000 for the language) -> dim_suppliers rows."""
    return (
        lfa1.select(
            pl.col("LIFNR").alias("supplier_id"),
            full_name(),
            pl.coalesce(pl.col("STCEG"), pl.col("STCD1")).alias("vat"),
            pl.col("LAND1").alias("country"),
        )
        .join(
            but000.select(
                pl.col("PARTNER").alias("supplier_id"),
                # Blank on most rows; store a null rather than an empty string.
                pl.col("BU_LANGU").replace("", None).alias("preferred_language"),
            ),
            on="supplier_id",
            how="left",
        )
        .with_columns(classify_is_financial())
        .unique(subset="supplier_id", keep="first")
        .select(SUPPLIER_COLUMNS)
    )


def build_business_units(t001: pl.DataFrame) -> pl.DataFrame:
    """T001 -> dim_business_units rows.

    The extract is already one client, so a duplicate bu_id means that filter
    stopped working — raise rather than silently collapse it the way the seed
    script's .unique() did.
    """
    rows = t001.select(
        pl.col("BUKRS").alias("bu_id"),
        pl.col("BUTXT").alias("name"),
        pl.col("STCEG").alias("vat"),
        pl.col("LAND1").alias("country"),
    ).select(BUSINESS_UNIT_COLUMNS)

    duplicates = rows.group_by("bu_id").len().filter(pl.col("len") > 1)
    if duplicates.height:
        ids = ", ".join(sorted(duplicates.get_column("bu_id").to_list()))
        raise ValueError(f"Duplicate bu_id in T001 extract: {ids}")
    return rows


def build_purchase_orders(ekko: pl.DataFrame) -> tuple[pl.DataFrame, list[str]]:
    """EKKO -> (rows to upsert, po_codes to delete).

    Deleted are the cancelled (LOEKZ) and the held, never-posted drafts (MEMORY).
    """
    gone = pl.col("LOEKZ").fill_null("").ne("") | pl.col("MEMORY").fill_null("").eq(PO_HELD_FLAG)
    delete_codes = ekko.filter(gone).get_column("EBELN").unique().sort().to_list()

    rows = (
        ekko.filter(~gone)
        .select(
            pl.col("EBELN").alias("po_code"),
            pl.col("LIFNR").alias("supplier_id"),
            pl.col("BUKRS").alias("bu_id"),
            pl.col("BEDAT").str.strptime(pl.Date, "%Y%m%d").alias("date"),
            pl.col("RLWRT").alias("value"),
            pl.col("WAERS").alias("currency"),
            pl.col("LASTCHANGEDATETIME").alias("source_changed_at"),
        )
        .unique(subset="po_code", keep="first")
        # Ascending, so MAX(source_changed_at) over the committed rows is always
        # a safe resume point. This is what replaces a run-log cursor table.
        .sort("source_changed_at")
        .select(PURCHASE_ORDER_COLUMNS)
    )
    return rows, delete_codes


def _blank_to_null(expr: pl.Expr) -> pl.Expr:
    """Trimmed text, with SAP's blank initial value as a null."""
    trimmed = expr.cast(pl.String).str.strip_chars()
    return pl.when(trimmed.fill_null("") == "").then(None).otherwise(trimmed)


def _joined_name(columns: tuple[str, ...]) -> pl.Expr:
    """BUT000 name lines joined by a space; null when every line is blank."""
    joined = (
        pl.concat_str([_blank_to_null(pl.col(_BUT000[c])) for c in columns], separator=" ", ignore_nulls=True)
        .str.replace_all(r"\s+", " ")
        .str.strip_chars()
    )
    return _blank_to_null(joined)


def partner_name() -> pl.Expr:
    """A partner's display name from BUT000.

    Organizations, persons and groups each fill a different set of columns, so
    take the first that has any; the search term is the last resort.
    """
    return pl.coalesce(
        _joined_name(("NAME_ORG1", "NAME_ORG2", "NAME_ORG3", "NAME_ORG4")),
        _joined_name(("NAME_FIRST", "NAME_LAST")),
        _joined_name(("NAME_GRP1", "NAME_GRP2")),
        _joined_name(("BU_SORT1",)),
    ).alias("name")


def _raise_on_duplicate_ids(ids: pl.DataFrame, source: str) -> None:
    """A duplicate client_id means the client filter stopped working."""
    duplicates = ids.group_by("client_id").len().filter(pl.col("len") > 1)
    if duplicates.height:
        listed = ", ".join(sorted(duplicates.get_column("client_id").to_list())[:10])
        raise ValueError(f"Duplicate client_id in {source} extract: {listed}")


def build_clients(kna1: pl.DataFrame, partners: pl.DataFrame) -> pl.DataFrame:
    """KNA1 (+ BUT000 for the name) -> dim_clients rows, one per customer.

    The name comes from BUT000, which holds it whole; KNA1 cuts it at 35
    characters a line, so its NAME1-NAME4 are only the fallback for a customer
    with no partner row. VAT is STCEG (EU registration), else STCD1 (domestic
    id). A customer with no name in either is left out: dim_clients.name is
    NOT NULL.
    """
    customers = kna1.select(
        pl.col("KUNNR").str.strip_chars().alias("client_id"),
        _blank_to_null(full_name()).alias("kna1_name"),
        pl.coalesce(_blank_to_null(pl.col("STCEG")), _blank_to_null(pl.col("STCD1"))).alias("vat"),
    )
    _raise_on_duplicate_ids(customers, "KNA1")

    names = partners.select(pl.col(_BUT000["PARTNER"]).str.strip_chars().alias("client_id"), partner_name())
    _raise_on_duplicate_ids(names, "BUT000")

    return (
        customers.join(names, on="client_id", how="left")
        .with_columns(pl.coalesce("name", "kna1_name").alias("name"))
        .drop_nulls("name")
        .sort("client_id")
        .select(CLIENT_COLUMNS)
    )


def _sap_date(column: str) -> pl.Expr:
    """A YYYYMMDD string as a date; SAP's '00000000' initial value is null."""
    return pl.col(column).str.strptime(pl.Date, "%Y%m%d", strict=False)


_INVOICE_KEY = ("bu_id", "fiscal_year", "document_nr", "line")


def _invoice_references(open_items: pl.DataFrame) -> pl.DataFrame:
    """Open credit lines that reduce one invoice, keyed by the invoice they
    point at (REBZG/REBZJ/REBZZ).

    `kind` is "amount_paid" for a partial payment (follow-on type 'Z', whatever
    its posting key) and "amount_credited" for a credit memo or invoice reversal
    (`CREDIT_MEMO_POSTING_KEYS`). A payment on account carries 'V' in REBZG,
    not an invoice, so it is not here. `reference_id` names the credit line
    itself, in invoice_id form.
    """
    col = {sap: pl.col(readable) for sap, readable in _BSEG.items()}
    is_payment = col["REBZT"] == "Z"
    is_credit_memo = col["BSCHL"].is_in(CREDIT_MEMO_POSTING_KEYS) & ~is_payment
    return open_items.filter((col["SHKZG"] == "H") & (is_payment | is_credit_memo)).select(
        col["BUKRS"].alias("bu_id"),
        col["REBZJ"].alias("fiscal_year"),
        col["REBZG"].alias("document_nr"),
        col["REBZZ"].alias("line"),
        pl.when(is_payment).then(pl.lit("amount_paid")).otherwise(pl.lit("amount_credited")).alias("kind"),
        col["WRBTR"].cast(_AMOUNT).alias("amount"),
        pl.concat_str([col["BUKRS"], col["GJAHR"], col["BELNR"], col["BUZEI"]], separator="/").alias("reference_id"),
    )


def orphan_invoice_references(open_items: pl.DataFrame, invoices: pl.DataFrame) -> list[str]:
    """Partial payments and credit memos pointing at no invoice in `invoices`.

    Their invoice has been cleared or is not an invoice line, so
    `build_open_invoices` nets them against nothing; this names them rather than
    drop them silently.
    """
    return (
        _invoice_references(open_items)
        .join(invoices.select(_INVOICE_KEY), on=_INVOICE_KEY, how="anti")
        .get_column("reference_id")
        .sort()
        .to_list()
    )


def build_open_invoices(open_items: pl.DataFrame) -> pl.DataFrame:
    """Open BSEG customer lines -> fct_invoices rows.

    An invoice is an open line with posting key 01, or a special G/L 'E' debit
    (key 09) — a receivable SAPF103 re-posted. Other debits (down payments,
    outgoing payments) are not invoices. What reduces an invoice are the open
    credit lines that point back at it (see `_invoice_references`): partial
    payments sum into `amount_paid`, credit memos into `amount_credited`, and
    `open_amount` is what is left. A payment on account is not tied to one
    invoice and is left out.

    `billing_document` is the SD billing number (VBELN) of an SD invoice — the
    number the customer sees on it (VBRK.XBLNR repeats it), standing in for
    BKPF.XBLNR, which is not replicated. `original_document_nr`: SAPF103
    re-postings carry the original document in the assignment number as
    document (10 digits), line (3) and fiscal year (4). Any other format is left
    null rather than guessed at. `issue_date` is the document date, which a
    re-posting copies from the original. `due_date` is SAP's own net due date.
    """
    key = _INVOICE_KEY
    col = {sap: pl.col(readable) for sap, readable in _BSEG.items()}
    zero = pl.lit(0).cast(_AMOUNT)

    references = _invoice_references(open_items)
    reductions = references.group_by(key).agg(
        pl.col("amount").filter(pl.col("kind") == kind).sum().cast(_AMOUNT).alias(kind)
        for kind in ("amount_paid", "amount_credited")
    )

    is_invoice = (col["BSCHL"] == INVOICE_POSTING_KEY) | (
        (col["UMSKZ"] == REPOSTED_RECEIVABLE_INDICATOR) & (col["BSCHL"] == REPOSTED_RECEIVABLE_POSTING_KEY)
    )
    rows = (
        open_items.filter(is_invoice)
        .select(
            col["BUKRS"].alias("bu_id"),
            col["GJAHR"].alias("fiscal_year"),
            col["BELNR"].alias("document_nr"),
            col["BUZEI"].alias("line"),
            col["KUNNR"].str.strip_chars().alias("client_id"),
            _blank_to_null(col["H_BLART"]).alias("document_type"),
            _blank_to_null(col["VBELN"]).alias("billing_document"),
            col["ZUONR"].str.extract(r"^(\d{10})\d{7}$").alias("original_document_nr"),
            _sap_date(_BSEG["H_BLDAT"]).alias("issue_date"),
            _sap_date(_BSEG["NETDT"]).alias("due_date"),
            col["WRBTR"].cast(_AMOUNT).alias("total_amount"),
            col["H_WAERS"].alias("currency"),
        )
        .join(reductions, on=key, how="left")
        .with_columns(pl.col("amount_paid", "amount_credited").fill_null(zero))
        .with_columns(
            (pl.col("total_amount") - pl.col("amount_paid") - pl.col("amount_credited"))
            .cast(_AMOUNT)
            .alias("open_amount"),
            pl.concat_str([pl.col(c) for c in key], separator="/").alias("invoice_id"),
        )
    )

    duplicates = rows.group_by("invoice_id").len().filter(pl.col("len") > 1)
    if duplicates.height:
        ids = ", ".join(sorted(duplicates.get_column("invoice_id").to_list())[:10])
        raise ValueError(f"Duplicate invoice_id in BSEG extract: {ids}")

    return rows.sort("invoice_id").select(INVOICE_COLUMNS)
