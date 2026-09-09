"""Purchase-order checks against the SAP master data.

Two sources, because the two questions live in different places. Whether a
supplier needs a PO is `dim_suppliers.is_financial` in Postgres:

    0  logistics  -> requires a PO
    1  financial  -> must not have one; a PO on the document is a misread
    2  both       -> may or may not have one, and it is checked if present

Whether a PO exists is SAP's own EKKO (purchase-order headers) read from the
lakehouse — the replicated table is the source of truth for what POs exist.

`supplier_requires_po` answers the model's yes/no. Telling 1 from 2 matters only
when the document actually carries a PO, so `decisions.missing_pos` reads the
flag itself through `supplier_is_financial`.

Only existence is checked today. Confirming that a PO's supplier and business
unit match the invoice's needs master data the lakehouse does not carry yet:
EKKO has `LIFNR` (zero-padded vendor number) and `BUKRS` (company code). Need
supplier and bu master data

Nothing here raises: these run on the routing critical path, so an unreachable
database or lakehouse must not stop an email from being processed. An unanswered
lookup falls back to the logistics case, which routes to review rather than
silently ingesting an unchecked invoice.
"""

from langchain_core.tools import tool
from loguru import logger

from utils.utils_db import normalize_key, normalize_sql, select_sync
from utils.utils_lakehouse import LakehouseRepository

# `dim_suppliers.is_financial`.
LOGISTICS = 0
FINANCIAL = 1
FINANCIAL_AND_LOGISTICS = 2

# The values that demand no PO. Everything else — including an unknown supplier,
# a NULL flag, or a failed lookup — requires one.
_NO_PO_NEEDED = (FINANCIAL, FINANCIAL_AND_LOGISTICS)

# SAP's EBELN is CHAR(10); anything longer cannot match.
_PO_CODE_LENGTH = 10


class PurchaseOrderRepository(LakehouseRepository):
    """SAP purchase-order headers — one row per PO, keyed on `EBELN`."""

    __table_name__ = "EKKO"


_purchase_orders = PurchaseOrderRepository()


def _query_is_financial(vat: str) -> int | None:
    """The supplier's `is_financial` flag, or None if unknown or unset."""
    query = f"""
    SELECT is_financial FROM dim_suppliers
    WHERE {normalize_sql("vat")} = $1
    LIMIT 1
    """
    rows = select_sync(query, [vat])
    return rows[0]["is_financial"] if rows else None


def supplier_is_financial(supplier_vat: str) -> int | None:
    """The supplier's `is_financial` flag, or None when it cannot be determined.

    Not a `@tool` — the model only needs the yes/no from `supplier_requires_po`,
    while `decisions.missing_pos` needs to tell 1 from 2 to decide what a PO on
    the document means. Returns None on an unknown supplier or a failed lookup,
    which callers treat as the logistics case.
    """
    vat = normalize_key(supplier_vat)
    if not vat:
        return None

    try:
        return _query_is_financial(vat)
    except Exception as exc:  # noqa: BLE001 - a DB blip must not break routing
        logger.warning(f"supplier_is_financial({vat}) failed, treating as unknown: {exc!r}")
        return None


@tool
def supplier_requires_po(supplier_vat: str) -> bool:
    """Whether invoices from this supplier require a Purchase Order reference.

    Args:
        supplier_vat: The supplier's VAT number.

    Returns:
        True if a PO is required, False if the supplier is in the exception list.
    """
    return supplier_is_financial(supplier_vat) not in _NO_PO_NEEDED


@tool
def po_exists(po_reference: str) -> bool:
    """Whether a purchase order reference exists in SAP.

    Args:
        po_reference: The purchase order number to check.

    Returns:
        True if the PO reference is known, otherwise False.
    """
    code = normalize_key(po_reference)
    if not code:
        return False

    if len(code) > _PO_CODE_LENGTH:
        # Not an error, but if every PO trips this the extracted references and
        # SAP's codes are in different formats — worth seeing in the logs.
        logger.debug(f"PO reference '{code}' exceeds EBELN's {_PO_CODE_LENGTH} chars")

    try:
        return _purchase_orders.exists("EBELN", code)
    except Exception as exc:  # noqa: BLE001 - a lookup blip must not break routing
        logger.warning(f"po_exists({code}) failed, treating the PO as unknown: {exc!r}")
        return False
