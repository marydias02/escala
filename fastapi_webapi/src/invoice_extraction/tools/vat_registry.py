"""Party lookups against the SAP master data in the lakehouse.

Clients are business units (`T001`, SAP's company codes); there is no separate
clients table. Each tool checks BOTH VATs against ONE registry — that is what
lets the model spot a supplier/client swap, so do not narrow it to one VAT per
table.

`supplier_preferred_language` is the exception to the shape above: it is keyed on
`supplier_id` rather than a VAT, and is not a `@tool` — the model is never asked
what language to reply in.

A lookup that cannot be answered returns False rather than raising: these run on
the routing critical path, and an unreachable lakehouse must not stop an email
from being processed.
"""

import polars as pl
from langchain_core.tools import tool
from loguru import logger

from utils.utils_db import normalize_key
from utils.utils_lakehouse import LakehouseRepository, normalize_expr

# SAP's one-character language keys, as the ISO 639-1 codes the reply rule uses.
# Anything outside this map is left unanswered, and the document's own language
# decides instead.
_SAP_LANGUAGES = {"P": "pt", "E": "en"}


class PartyRepository(LakehouseRepository):
    """A SAP table identifying a party, addressable by VAT.

    Subclasses name their id/name/VAT columns, so callers work in `id`/`name`/
    `vat` terms and stay out of SAP's column naming.
    """

    id_column: str = ""
    name_column: str = ""
    vat_columns: tuple[str, ...] = ()

    def by_vat(self, vat: str) -> list[dict[str, str]]:
        """Every party registered under `vat`, as `id`/`name`/`vat` dicts."""
        return self.rows_by_normalized(
            self.vat_columns,
            vat,
            {
                "id": pl.col(self.id_column),
                "name": pl.col(self.name_column),
                "vat": pl.coalesce([normalize_expr(column).replace("", None) for column in self.vat_columns]),
            },
        )


class SupplierRepository(PartyRepository):
    """SAP vendor master — one row per supplier, keyed on `LIFNR`."""

    __table_name__ = "LFA1"

    id_column = "LIFNR"
    name_column = "NAME1"
    # In precedence order: the EU VAT registration, then the domestic tax id
    # carried by suppliers that have no EU one.
    vat_columns = ("STCEG", "STCD1")


class BusinessUnitRepository(PartyRepository):
    """SAP company codes — one row per business unit, keyed on `BUKRS`."""

    __table_name__ = "T001"

    id_column = "BUKRS"
    name_column = "BUTXT"
    vat_columns = ("STCEG",)


class BusinessPartnerRepository(LakehouseRepository):
    """SAP business partners — one row per partner, keyed on `PARTNER`."""

    __table_name__ = "BUT000"


suppliers = SupplierRepository()
business_units = BusinessUnitRepository()
_business_partners = BusinessPartnerRepository()


def _both_in(repository: LakehouseRepository, client_vat: str, supplier_vat: str) -> tuple[bool, bool]:
    """Whether each VAT appears in `repository`, in one scan."""
    client = normalize_key(client_vat)
    supplier = normalize_key(supplier_vat)

    lookup = [vat for vat in (client, supplier) if vat]
    if not lookup:
        return False, False

    try:
        known = repository.known_normalized(repository.vat_columns, lookup)
    except Exception as exc:  # noqa: BLE001 - a lookup blip must not break routing
        logger.warning(f"{repository.table} VAT lookup failed, treating both as unknown: {exc!r}")
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
    return _both_in(business_units, client_vat, supplier_vat)


@tool
def verify_supplier_nif(client_vat: str, supplier_vat: str) -> tuple[bool, bool]:
    """Verify whether the NIFs recovered are in the list of known suppliers.

    Args:
        client_vat: The unique client VAT number
        supplier_vat: The unique supplier VAT number

    Returns:
        True, True if the client and supplier are in the list of known suppliers, otherwise False
    """
    return _both_in(suppliers, client_vat, supplier_vat)


def supplier_preferred_language(supplier_id: str | None) -> str | None:
    """The supplier's preferred reply language, as a lowercase ISO 639-1 code.

    Keyed on `supplier_id`, which `nodes.validate.resolve_registry_ids` fills
    only on a registry match — so an id in hand already means the supplier is
    identified, and this is a straight key read rather than a second attempt at
    matching them. `LIFNR` is `BUT000.PARTNER`, so the id carries over as is.

    None when there is no id, no preference recorded against it, a key outside
    `_SAP_LANGUAGES`, or a failed lookup. `decisions.reply_language` treats them
    alike: none says what language to write in, so it falls back to the document.
    """
    if not supplier_id:
        return None

    try:
        row = _business_partners.get_by("PARTNER", str(supplier_id))
    except Exception as exc:  # noqa: BLE001 - a lookup blip must not break routing
        logger.warning(f"supplier_preferred_language({supplier_id}) failed, treating as unknown: {exc!r}")
        return None

    language = row.get("BU_LANGU") if row else None
    return _SAP_LANGUAGES.get(language.strip().upper()) if language else None
