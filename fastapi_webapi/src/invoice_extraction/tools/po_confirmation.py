from langchain_core.tools import tool

# Simulated registries. Swapping in a real database
# later is a single-file change — the tool signatures stay the same.
NO_PO_NEEDED_SUPPLIERS = [
    "PT501925350",
]

KNOWN_PURCHASE_ORDERS = []


@tool
def supplier_requires_po(supplier_vat: str) -> bool:
    """Whether invoices from this supplier require a Purchase Order reference.

    Args:
        supplier_vat: The supplier's VAT number.

    Returns:
        True if a PO is required, False if the supplier is in the exception list.
    """
    return supplier_vat not in NO_PO_NEEDED_SUPPLIERS


@tool
def po_exists(po_reference: str) -> bool:
    """Whether a purchase order reference exists in the PO system.

    Args:
        po_reference: The purchase order number to check.

    Returns:
        True if the PO reference is known, otherwise False.
    """
    return po_reference in KNOWN_PURCHASE_ORDERS
