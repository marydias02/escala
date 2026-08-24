"""Party lookups against the SAP master data in Postgres.

Clients are business units (`dim_business_units`); there is no separate clients
table. Each tool checks BOTH VATs against ONE registry — that is what lets the
model spot a supplier/client swap, so do not narrow it to one VAT per table.

A lookup that cannot be answered returns False rather than raising: these run on
the routing critical path, and an unreachable database must not stop an email
from being processed. False is also what an empty table returns, which is the
honest answer while SAP master data has not landed yet.
"""

from langchain_core.tools import tool
from loguru import logger

from utils.utils_db import normalize_key, normalize_sql, select_sync


def _known_vats(table: str, vats: list[str]) -> set[str]:
    """The normalized VATs among `vats` that `table` knows about."""
    query = f"""
    SELECT {normalize_sql("vat")} AS vat
    FROM {table}
    WHERE {normalize_sql("vat")} = ANY($1::text[])
    """
    return {row["vat"] for row in select_sync(query, [vats])}


def _both_in(table: str, client_vat: str, supplier_vat: str) -> tuple[bool, bool]:
    """Whether each VAT appears in `table`, in one query."""
    client = normalize_key(client_vat)
    supplier = normalize_key(supplier_vat)

    lookup = [vat for vat in (client, supplier) if vat]
    if not lookup:
        return False, False

    try:
        known = _known_vats(table, lookup)
    except Exception as exc:  # noqa: BLE001 - a DB blip must not break routing
        logger.warning(f"{table} VAT lookup failed, treating both as unknown: {exc!r}")
        return False, False

    return client in known, supplier in known


@tool
def verify_client_nif(client_vat: str, supplier_vat: str) -> tuple[bool, bool]:
    """Verify whether the NIFs recovered are in the list of known clients.

    Args:
        client_vat: The unique client VAT number
        supplier_vat: The unique supplier VAT number

    Returns:
        True, True if the client and supplier vats are in the list of known clients, otherwise False
    """
    return _both_in("dim_business_units", client_vat, supplier_vat)


@tool
def verify_supplier_nif(client_vat: str, supplier_vat: str) -> tuple[bool, bool]:
    """Verify whether the NIFs recovered are in the list of known suppliers.

    Args:
        client_vat: The unique client VAT number
        supplier_vat: The unique supplier VAT number

    Returns:
        True, True if the client and supplier are in the list of known suppliers, otherwise False
    """
    return _both_in("dim_suppliers", client_vat, supplier_vat)
