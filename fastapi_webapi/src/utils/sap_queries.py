"""Business-partner and open-item lookups against SAP tables replicated to the lakehouse.

BUT000 is SAP's central Business Partner table — one row per partner, holding
the category (person / organization / group), names, grouping, search terms and
the central block/deletion flags. See `SAPTableMetadata(table_name="BUT000")`
for the full column meanings.

`query_business_partners` wraps `utils.utils_lakehouse.scan_table` with the
filters these lookups actually need (by partner number, by name, by category)
and keeps the Delta read lazy so column/row pushdown still applies. Columns that
the replicated table does not carry are ignored rather than raising, so a
partial replication still returns what it has.

`query_customers` does the same for KNA1, the customer master: one row per
customer, with its VAT, address and block/deletion flags.

`query_open_accounts_receivable` does the same for BSEG (accounting document
line items), selecting the customer lines that have not been cleared yet.

`get_customer` combines them for one customer: its customer master record, its
business-partner record (which holds the full name) and its open receivables.

Result columns are named after their meaning in the lakehouse tables mapping
(`SAPTableMetadata.readable_column_names`), e.g. `customer_number`.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd
import polars as pl
from loguru import logger

from utils.lakehouse_tables_column_mappings import SAPTableMetadata
from utils.utils_lakehouse import scan_table

_TABLE = "BUT000"
_METADATA = SAPTableMetadata(table_name=_TABLE)

_BSEG_TABLE = "BSEG"
_BSEG_METADATA = SAPTableMetadata(table_name=_BSEG_TABLE)

_KNA1_TABLE = "KNA1"
_KNA1_METADATA = SAPTableMetadata(table_name=_KNA1_TABLE)

#: Free-text name search spans every name-bearing column: organizations, persons
#: and groups each populate a different set depending on BUT000.TYPE.
BUSINESS_PARTNER_NAME_COLUMNS: tuple[str, ...] = (
    "NAME_ORG1",
    "NAME_ORG2",
    "NAME_ORG3",
    "NAME_ORG4",
    "NAME_FIRST",
    "NAME_LAST",
    "NAME_LAST2",
    "NAMEMIDDLE",
    "NAME_GRP1",
    "NAME_GRP2",
    "BU_SORT1",
    "BU_SORT2",
)

#: KNA1 name lines, plus the search term. Each line is cut at 35 characters;
#: BUT000 holds the full name.
CUSTOMER_NAME_COLUMNS: tuple[str, ...] = ("NAME1", "NAME2", "NAME3", "NAME4", "SORTL")

#: BUT000.TYPE codes.
PARTNER_CATEGORY_PERSON = "1"
PARTNER_CATEGORY_ORGANIZATION = "2"
PARTNER_CATEGORY_GROUP = "3"

#: BSEG.KOART account type of a customer (accounts receivable) line.
ACCOUNT_TYPE_CUSTOMER = "D"

#: The productive SAP client. The lakehouse also replicates client 000 (SAP's
#: reference client) for some tables, whose keys collide with 100's.
SAP_CLIENT = "100"


def _as_str_list(value: str | Iterable[str] | None) -> list[str]:
    """Normalize a scalar / iterable / None argument to a list of trimmed strings."""
    if value is None:
        return []
    values = [value] if isinstance(value, str) else list(value)
    return [str(v).strip() for v in values if v is not None and str(v).strip()]


def _name_contains(lf: pl.LazyFrame, table: str, name_columns: Sequence[str], name: str) -> pl.LazyFrame:
    """Keep rows where any of `name_columns` contains `name`, case-insensitively."""
    needle = name.strip().lower()
    available = set(lf.collect_schema().names())
    columns = [c for c in name_columns if c in available]
    if not columns:
        logger.warning(f"{table} carries none of the expected name columns; ignoring name filter")
        return lf
    matches = pl.any_horizontal(
        pl.col(c).cast(pl.Utf8).str.to_lowercase().str.contains(needle, literal=True).fill_null(False) for c in columns
    )
    return lf.filter(matches)


def _flag_is_set(column: str) -> pl.Expr:
    """SAP boolean-ish flags come across as 'X' / '' (occasionally true/false)."""
    normalized = pl.col(column).cast(pl.Utf8).str.strip_chars().str.to_lowercase()
    return normalized.is_in(["x", "true", "1"])


def _is_blank(column: str) -> pl.Expr:
    """SAP initial values come across as null or an empty / space-padded string."""
    return pl.col(column).cast(pl.Utf8).str.strip_chars().fill_null("") == ""


def _select_readable(
    lf: pl.LazyFrame,
    metadata: SAPTableMetadata,
    columns: Sequence[str] | None,
    limit: Optional[int],
) -> pl.DataFrame:
    """Project, cap and collect `lf`, naming its columns after their mapped meaning.

    `columns` takes SAP names ("KUNNR") or readable ones ("customer_number") and
    defaults to the table's documented columns; names the table does not carry are
    dropped, and a column named twice (in either form) appears once. Output columns
    are `metadata.readable_column_names`; a column the mapping does not document
    keeps its SAP name, lower-cased.
    """
    readable = metadata.readable_column_names
    sap_by_readable = {name: column for column, name in readable.items()}
    available = set(lf.collect_schema().names())

    projection = [sap_by_readable.get(c, c) for c in columns] if columns is not None else metadata.column_names
    projection = [c for c in dict.fromkeys(projection) if c in available]
    if projection:
        lf = lf.select(projection)

    if limit is not None:
        lf = lf.limit(limit)

    # Filters run on SAP's upper-case names; callers get the readable ones.
    lf = lf.rename({c: readable.get(c, c.lower()) for c in lf.collect_schema().names()})
    return lf.collect()


def query_business_partners(
    *,
    partner: str | Sequence[str] | None = None,
    name: str | None = None,
    category: str | Sequence[str] | None = None,
    columns: Sequence[str] | None = None,
    exclude_blocked: bool = False,
    exclude_deleted: bool = True,
    client: Optional[str] = SAP_CLIENT,
    limit: Optional[int] = 100,
) -> pl.DataFrame:
    """Business partner rows from BUT000 matching the given filters.

    Every filter is optional and they combine with AND. With no filter this
    returns the first `limit` partners; pass `limit=None` for the whole table
    (large — BUT000 holds every partner in the client).

    Args:
        partner: One partner number or a list of them; exact match on `PARTNER`.
            Values are trimmed but not zero-padded, so pass them in the format
            SAP stores (typically 10 chars, left zero-padded).
        name: Case-insensitive substring matched against every name column in
            `BUSINESS_PARTNER_NAME_COLUMNS` (organization, person and group).
        category: Business partner category code(s) on `TYPE` — "1" person,
            "2" organization, "3" group (see the `PARTNER_CATEGORY_*` constants).
        columns: Projection, by SAP name ("PARTNER") or readable name
            ("business_partner_number"). Defaults to the documented BUT000
            columns; pass an explicit list to widen or narrow it. Unknown names
            are dropped.
        exclude_blocked: Drop partners with the central block flag (`XBLCK`).
        exclude_deleted: Drop partners flagged for central deletion (`XDELE`).
        client: SAP client on `CLIENT` (BUT000's name for `MANDT`). `None`
            reads every client.
        limit: Row cap, applied last. `None` means no cap.

    Returns:
        A polars DataFrame, empty if nothing matched. Columns are named after
        their meaning in the BUT000 mapping, in snake_case (`PARTNER` ->
        `business_partner_number`, `NAME_ORG1` -> `organization_name_line_1`; see
        `SAPTableMetadata.readable_column_names`). Columns the mapping does not
        document keep their SAP name, lower-cased.
    """
    lf = scan_table(_TABLE)
    available = set(lf.collect_schema().names())

    if client is not None:
        lf = lf.filter(pl.col("CLIENT") == client)

    partners = _as_str_list(partner)
    if partners:
        lf = lf.filter(pl.col("PARTNER").cast(pl.Utf8).is_in(partners))

    categories = _as_str_list(category)
    if categories:
        lf = lf.filter(pl.col("TYPE").cast(pl.Utf8).is_in(categories))

    if name and name.strip():
        lf = _name_contains(lf, _TABLE, BUSINESS_PARTNER_NAME_COLUMNS, name)

    if exclude_blocked and "XBLCK" in available:
        lf = lf.filter(~_flag_is_set("XBLCK"))
    if exclude_deleted and "XDELE" in available:
        lf = lf.filter(~_flag_is_set("XDELE"))

    return _select_readable(lf, _METADATA, columns, limit)


def get_business_partner(
    partner: str,
    *,
    columns: Sequence[str] | None = None,
) -> Optional[dict[str, Any]]:
    """A single business partner by exact `PARTNER`, or None if there is no match.

    Unlike `query_business_partners`, this does not filter out centrally deleted
    partners — an explicit number lookup should still find a flagged record. The
    dict is keyed by the same readable column names.
    """
    if not partner or not partner.strip():
        return None
    df = query_business_partners(
        partner=partner.strip(),
        columns=columns,
        exclude_deleted=False,
        limit=1,
    )
    return df.row(0, named=True) if df.height > 0 else None


def query_customers(
    *,
    customer: str | Sequence[str] | None = None,
    name: str | None = None,
    columns: Sequence[str] | None = None,
    exclude_blocked: bool = False,
    exclude_deleted: bool = True,
    client: Optional[str] = SAP_CLIENT,
    limit: Optional[int] = 100,
) -> pl.DataFrame:
    """Customer master rows from KNA1 matching the given filters.

    Every customer SAP holds, whether or not anything was ever posted to it.
    Every filter is optional and they combine with AND; `limit=None` returns
    the whole table.

    Args:
        customer: One customer number or a list of them; exact match on `KUNNR`.
            Values are trimmed but not zero-padded, so pass them in the format
            SAP stores (10 chars, left zero-padded, e.g. "0100008647").
        name: Case-insensitive substring matched against `CUSTOMER_NAME_COLUMNS`.
            KNA1 cuts each name line at 35 characters; to search the full name,
            use `query_business_partners` (KUNNR is the BUT000 PARTNER).
        columns: Projection, by SAP name ("KUNNR") or readable name
            ("customer_number"). Defaults to the documented KNA1 columns; pass an
            explicit list to widen or narrow it. Unknown names are dropped.
        exclude_blocked: Drop customers with the central posting block (`SPERR`).
        exclude_deleted: Drop customers flagged for central deletion (`LOEVM`).
        client: SAP client on `MANDT`. `None` reads every client.
        limit: Row cap, applied last. `None` means no cap.

    Returns:
        A polars DataFrame, empty if nothing matched. Columns are named after
        their meaning in the KNA1 mapping, in snake_case (`KUNNR` ->
        `customer_number`, `STCEG` -> `vat_registration_number`; see
        `SAPTableMetadata.readable_column_names`). Columns the mapping does not
        document keep their SAP name, lower-cased.
    """
    lf = scan_table(_KNA1_TABLE)
    available = set(lf.collect_schema().names())

    if client is not None:
        lf = lf.filter(pl.col("MANDT") == client)

    customers = _as_str_list(customer)
    if customers:
        lf = lf.filter(pl.col("KUNNR").cast(pl.Utf8).is_in(customers))

    if name and name.strip():
        lf = _name_contains(lf, _KNA1_TABLE, CUSTOMER_NAME_COLUMNS, name)

    if exclude_blocked and "SPERR" in available:
        lf = lf.filter(~_flag_is_set("SPERR"))
    if exclude_deleted and "LOEVM" in available:
        lf = lf.filter(~_flag_is_set("LOEVM"))

    return _select_readable(lf, _KNA1_METADATA, columns, limit)


def get_customer_master(
    customer: str,
    *,
    columns: Sequence[str] | None = None,
) -> Optional[dict[str, Any]]:
    """A single KNA1 customer by exact `KUNNR`, or None if there is no match.

    Like `get_business_partner`, a customer flagged for deletion is still
    returned. The dict is keyed by the same readable column names.
    """
    if not customer or not customer.strip():
        return None
    df = query_customers(customer=customer.strip(), columns=columns, exclude_deleted=False, limit=1)
    return df.row(0, named=True) if df.height > 0 else None


def query_open_accounts_receivable(
    *,
    customer: str | Sequence[str] | None = None,
    company_code: str | Sequence[str] | None = None,
    fiscal_year: str | Sequence[str] | None = None,
    columns: Sequence[str] | None = None,
    client: Optional[str] = SAP_CLIENT,
    limit: Optional[int] = 100,
) -> pl.DataFrame:
    """Open customer line items (accounts receivable) from BSEG.

    An open item is a customer line (`KOART = 'D'`) with no clearing document
    (`AUGBL` blank): posted to the customer but not yet matched against a
    payment or credit memo. It is the set SAP's customer open-item index (BSID)
    holds. Every filter is optional and they combine with AND; `limit=None`
    returns everything (BSEG is large).

    Args:
        customer: One customer number or a list of them; exact match on `KUNNR`.
            Values are trimmed but not zero-padded, so pass them in the format
            SAP stores (10 chars, left zero-padded, e.g. "0100008647").
        company_code: Company code(s) on `BUKRS`.
        fiscal_year: Fiscal year(s) on `GJAHR`, e.g. "2026".
        columns: Projection, by SAP name ("KUNNR") or readable name
            ("customer_number"). Defaults to the documented BSEG columns; pass an
            explicit list to widen or narrow it. Unknown names are dropped.
        client: SAP client on `MANDT`. `None` reads every client.
        limit: Row cap, applied last. `None` means no cap.

    Returns:
        A polars DataFrame, empty if nothing matched. Columns are named after
        their meaning in the BSEG mapping, in snake_case (`KUNNR` ->
        `customer_number`, `DMBTR` -> `amount_in_local_currency`; see
        `SAPTableMetadata.readable_column_names`). Columns the mapping does not
        document keep their SAP name, lower-cased.

    Caveats when reading the result:
        - `amount_in_local_currency` (`DMBTR`) and `amount_in_document_currency`
          (`WRBTR`) are unsigned. `debit_credit_indicator` (`SHKZG`) gives the
          direction: 'S' (debit) is money the customer owes, 'H' (credit) is a
          credit memo or payment on account. Apply the sign before summing.
        - Every kind of customer line is included; `posting_key` (`BSCHL`)
          tells them apart: 01 invoice, 11 credit memo, 15 incoming payment,
          09/19 special G/L debit/credit (`UMSKZ` 'E' re-posted receivables,
          'A' down payments). As replicated since 2026-09-25, ordinary lines
          (`UMSKZ` blank) are present only while open; only the special G/L 'E'
          lines carry cleared history.
        - BSEG repeats a few header fields on every line: `document_type`
          (`H_BLART`), `document_date` (`H_BLDAT`), `posting_date` (`H_BUDAT`)
          and `currency_key_of_the_document` (`H_WAERS`, the currency of
          `amount_in_document_currency`). The header reference (`XBLNR`) lives
          in BKPF, which is not replicated; for SD invoices (`H_BLART` 'RV')
          `billing_document` (`VBELN`) is the number the customer sees.
          Payment terms are `ZTERM`, `ZFBDT`, `ZBD*`; SAP's resulting net due
          date is `due_date_for_net_payment` (`NETDT`).
    """
    lf = scan_table(_BSEG_TABLE).filter((pl.col("KOART") == ACCOUNT_TYPE_CUSTOMER) & _is_blank("AUGBL"))

    if client is not None:
        lf = lf.filter(pl.col("MANDT") == client)

    customers = _as_str_list(customer)
    if customers:
        lf = lf.filter(pl.col("KUNNR").cast(pl.Utf8).is_in(customers))

    company_codes = _as_str_list(company_code)
    if company_codes:
        lf = lf.filter(pl.col("BUKRS").cast(pl.Utf8).is_in(company_codes))

    fiscal_years = _as_str_list(fiscal_year)
    if fiscal_years:
        lf = lf.filter(pl.col("GJAHR").cast(pl.Utf8).is_in(fiscal_years))

    return _select_readable(lf, _BSEG_METADATA, columns, limit)


@dataclass(frozen=True)
class CustomerData:
    """One customer's master data and, when requested, its open receivables.

    `customer_master` is the KNA1 row keyed by readable column names (as
    `get_customer_master` returns it) — VAT, address, blocks. `business_partner`
    is the BUT000 row (as `get_business_partner` returns it), the source of the
    full name, which KNA1 cuts at 35 characters a line. Either is None if its
    table has no row for the number. `open_receivables` is
    `query_open_accounts_receivable`'s frame for the customer — empty if nothing
    is open, None if it was not requested.
    """

    customer_number: str
    customer_master: Optional[dict[str, Any]]
    business_partner: Optional[dict[str, Any]]
    open_receivables: Optional[pl.DataFrame] = None


def get_customer(customer: str, *, include_open_receivables: bool = True) -> Optional[CustomerData]:
    """A customer's master data and open receivables, or None if SAP knows
    nothing about the number.

    The customer master is the KNA1 row; the BUT000 row alongside it carries
    the full name (a customer number is its business partner number). Like
    `get_customer_master` and `get_business_partner`, a customer flagged for
    deletion or blocked is still returned — check
    `central_deletion_flag_for_the_master_record` and `central_posting_block` on
    the master record. Pass the number in the format SAP stores (10 chars, left
    zero-padded, e.g. "0100008647").

    Open receivables are every uncleared customer line in BSEG, with all the
    caveats of `query_open_accounts_receivable` (unsigned amounts). Pass
    `include_open_receivables=False` for the master data alone.
    """
    if not customer or not customer.strip():
        return None
    number = customer.strip()

    master = get_customer_master(number)
    partner = get_business_partner(number)
    receivables = query_open_accounts_receivable(customer=number, limit=None) if include_open_receivables else None
    if master is None and partner is None and (receivables is None or receivables.is_empty()):
        return None
    return CustomerData(
        customer_number=number, customer_master=master, business_partner=partner, open_receivables=receivables
    )


if __name__ == "__main__":
    FISCAL_YEAR: Optional[str] = None  # e.g. "2026" to restrict the ranking to one fiscal year; None = every year

    # Deleted partners are kept: a left merge would otherwise leave them nameless.
    bp_df = query_business_partners(exclude_deleted=False, limit=None).to_pandas()
    ar_df = query_open_accounts_receivable(limit=None).to_pandas()
    # Decimal -> float so pandas can sum the amounts.
    ar_df[["amount_in_local_currency", "amount_in_document_currency"]] = ar_df[
        ["amount_in_local_currency", "amount_in_document_currency"]
    ].astype(float)

    # A person has no organization name: fall back to first + last name.
    org_name = (bp_df.organization_name_line_1.fillna("") + " " + bp_df.organization_name_line_2.fillna("")).str.strip()
    person_name = (bp_df.first_name.fillna("") + " " + bp_df.last_name.fillna("")).str.strip()
    bp_df["customer_name"] = org_name.where(org_name != "", person_name)

    # Open invoices: debit ('S') lines only, since 'H' lines are credit memos / payments. A document number is only
    # unique within its company code and fiscal year, hence the company_code/fiscal_year/number key.
    invoices_df = ar_df[
        (ar_df.debit_credit_indicator == "S") & ((ar_df.fiscal_year == FISCAL_YEAR) if FISCAL_YEAR else True)
    ].assign(invoice=lambda d: d.company_code + "/" + d.fiscal_year + "/" + d.accounting_document_number)

    top_clients_df = (
        invoices_df.groupby("customer_number")
        .agg(nr_open_invoices=("invoice", "nunique"))
        .join(bp_df.set_index("business_partner_number").customer_name)
        .sort_values(by=["nr_open_invoices"], ascending=False)
    )

    # Open invoices of the client with the most, with what has been paid against each line so far.
    # A partial payment is a credit line (follow-on type 'Z') that points back at the invoice line it pays down
    # (REBZG/REBZJ/REBZZ). An invoice with none is unpaid: an open item has no clearing document, so no receipt yet.
    top_customer = top_clients_df.index[0]

    invoice_key = [
        "company_code",
        "accounting_document_number",
        "fiscal_year",
        "line_item_number_within_the_accounting_document",
    ]
    paid_df = (
        ar_df[(ar_df.debit_credit_indicator == "H") & (ar_df.follow_on_document_type == "Z")]
        .groupby(
            [
                "company_code",
                "number_of_the_invoice_the_transaction_belongs_to",
                "fiscal_year_of_the_relevant_invoice",
                "line_item_in_the_relevant_invoice",
            ]
        )
        .agg(
            amount_paid=("amount_in_document_currency", "sum"),
            receipt=("accounting_document_number", lambda docs: ", ".join(sorted(docs.unique()))),
        )
        .rename_axis(invoice_key)
        .reset_index()
    )

    top_client_invoices_df = (
        invoices_df[invoices_df.customer_number == top_customer]
        .merge(paid_df, on=invoice_key, how="left")
        .assign(
            customer_name=top_clients_df.customer_name[top_customer],
            amount_paid=lambda d: d.amount_paid.fillna(0.0),
            receipt=lambda d: d.receipt.fillna(""),
            # SAPF103 re-postings carry the original document in the assignment number: document (10 digits), line (3)
            # and fiscal year (4). Any other assignment format is left blank rather than guessed at.
            original_document_nr=lambda d: d.assignment_number.str.extract(r"^(\d{10})\d{7}$", expand=False).fillna(""),
            # A re-posting keeps the original's document date, so this is the invoice date. The line's own posting date
            # is the re-posting run and not an issue date.
            issue_date=lambda d: pd.to_datetime(d.document_date, format="%Y%m%d", errors="coerce"),
        )
        .rename(
            columns={
                "accounting_document_number": "document_nr",
                "line_item_number_within_the_accounting_document": "line",
                "amount_in_document_currency": "total_amount",
                "currency_key_of_the_document": "currency",
            }
        )[
            [
                "customer_number",
                "customer_name",
                "document_nr",
                "line",
                "original_document_nr",
                "issue_date",
                "total_amount",
                "currency",
                "amount_paid",
                "receipt",
            ]
        ]
        .sort_values(by=["document_nr", "line"])
    )
