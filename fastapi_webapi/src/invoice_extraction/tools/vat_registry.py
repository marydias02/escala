from langchain_core.tools import tool

# Simulated registries. Hoisted to module level so swapping in a real database
# later is a single-file change — the tool signatures stay the same.
KNOWN_CLIENT_VATS = [
    "PT511034750",
    "PT511011911",
    "PT509225918",
    "PT513286004",
    "PT511051000",
    "PT511070357",
    "PT513791345",
]

KNOWN_SUPPLIER_VATS = [
    "PT512046158",
    "PT500697370",
    "LU19578473",
    "PT501925350",
    "NL800822274B01",
]


@tool
def verify_client_nif(client_vat: str, supplier_vat: str) -> tuple[bool, bool]:
    """Verify whether the NIFs recovered are in the list of known clients.

    Args:
        client_vat: The unique client VAT number
        supplier_vat: The unique supplier VAT number

    Returns:
        True, True if the client and supplier vats are in the list of known clients, otherwise False
    """
    client = client_vat in KNOWN_CLIENT_VATS
    supplier = supplier_vat in KNOWN_CLIENT_VATS

    return client, supplier


@tool
def verify_supplier_nif(client_vat: str, supplier_vat: str) -> tuple[bool, bool]:
    """Verify whether the NIFs recovered are in the list of known suppliers.

    Args:
        client_vat: The unique client VAT number
        supplier_vat: The unique supplier VAT number

    Returns:
        True, True if the client and supplier are in the list of known suppliers, otherwise False
    """
    client = client_vat in KNOWN_SUPPLIER_VATS
    supplier = supplier_vat in KNOWN_SUPPLIER_VATS

    return client, supplier