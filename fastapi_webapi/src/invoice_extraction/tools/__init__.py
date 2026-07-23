from invoice_extraction.tools.vat_registry import verify_client_nif, verify_supplier_nif

VALIDATION_TOOLS = [verify_client_nif, verify_supplier_nif]

__all__ = [
    "VALIDATION_TOOLS",
    "verify_client_nif",
    "verify_supplier_nif",
]