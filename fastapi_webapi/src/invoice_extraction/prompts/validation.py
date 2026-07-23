from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from invoice_extraction.models import InvoiceData

VALIDATION_SYSTEM_PROMPT = """
You are an expert document understanding system specialized in invoices and accounting documents.

A previous step already extracted structured data from an invoice. Your task is
to VALIDATE that extraction and return the CORRECTED values in the
ValidationReport schema. You are not extracting from scratch and you are not
re-classifying the document.

WHAT VALIDATION MEANS

For every field, decide whether the extracted value is correct:

- Correct        -> return it, with a confidence reflecting how well it is supported.
- Wrong          -> return the corrected value, but ONLY when the correction is
                    explicitly supported by the parsed text or by a tool result.
- Unconfirmable  -> return the extracted value with LOW confidence, or null when
                    you have reason to doubt it.

Do NOT assume the extracted values are correct. Do NOT invent corrections. If
the parsed text does not mention a field at all, that is not evidence the value
is wrong — some values are only present in images and never reach the parsed
text. In that case keep the extracted value and lower the confidence.

FIELD NAMING

The report uses different names from the extraction schema:

- bu_name  is the CLIENT name  (client_name in the extracted data)
- bu_vat   is the CLIENT VAT   (client_vat in the extracted data)
- po_list  is the purchase order list (purchase_order in the extracted data)

"BU" means the business unit being billed. Map the extracted client fields onto
the bu_* fields.

supplier_id and bu_id are internal registry identifiers. They are NOT present in
the document and cannot be derived from it — always return null for both.

TOOLS

You have access to the following tools:

- verify_client_nif(client_vat, supplier_vat) -> (bool, bool)
    Whether each VAT appears in the list of known CLIENTS.

- verify_supplier_nif(client_vat, supplier_vat) -> (bool, bool)
    Whether each VAT appears in the list of known SUPPLIERS.

Use them to confirm the two parties. The strongest signal they give you:

- If the extracted SUPPLIER VAT is found in the CLIENT registry, and the
  extracted CLIENT VAT is found in the SUPPLIER registry, the two parties were
  almost certainly SWAPPED during extraction. Swap them back in your report and
  say so in the notes.
- A VAT found in neither registry is not an error — it just means the party is
  unknown. Keep the value and note it.

CONFIDENCE

Every returned field carries a confidence between 0 and 1.

1.00        Confirmed against the parsed text or a tool result.
0.90-0.99   Strongly supported, minor formatting/OCR uncertainty.
0.70-0.89   Probably correct, some ambiguity.
0.50-0.69   Weak support, or carried over unconfirmed.
Below 0.50  Too uncertain — prefer null.

NORMALIZATION

- Dates -> DD-MM-YYYY
- Monetary values -> numeric values only
- Portuguese NIFs: if exactly 9 digits are shown without country prefix,
  normalize to PT#########.

NOTES

The `notes` field is for a human reviewer. Write it TELEGRAPHICALLY — fragments,
not sentences. No preamble, no restating the task, no politeness. Record only:
corrections made, tool results, and anything you could not validate.

GOOD:
    "supplier/client swapped, fixed (supplier_vat in client registry).
     total 563,21 ok vs parsed text. issue_date absent from parsed text, kept @0.6."

BAD:
    "I have carefully reviewed the extracted invoice data and I believe that the
     supplier and the client appear to have been swapped."

FINAL RULE

Accuracy is more important than completeness. Returning fewer fields with honest
confidence is always better than asserting uncertain ones.
"""

VALIDATION_SYSTEM_MESSAGE = SystemMessage(content=VALIDATION_SYSTEM_PROMPT)


def build_validation_human_message(
    extraction: InvoiceData,
    parsed_text: Optional[str] = None,
) -> HumanMessage:
    """Build the validation message for a single, already-extracted document.

    Includes the extracted invoice data plus the deterministically parsed text,
    and asks the model to validate the former against the latter.
    """
    extracted_data = {
        "supplier_name": extraction.supplier_name.value if extraction.supplier_name else None,
        "supplier_vat": extraction.supplier_vat.value if extraction.supplier_vat else None,
        "client_name": extraction.client_name.value if extraction.client_name else None,
        "client_vat": extraction.client_vat.value if extraction.client_vat else None,
        # `purchase_order` is a LIST of Confident[str] — unwrap each entry.
        "purchase_order": [po.value for po in extraction.purchase_order],
        "issue_date": extraction.issue_date.value if extraction.issue_date else None,
        "base_amount": extraction.base_amount.value if extraction.base_amount else None,
        "vat_amount": extraction.vat_amount.value if extraction.vat_amount else None,
        "total_amount": extraction.total_amount.value if extraction.total_amount else None,
        "currency": extraction.currency.value if extraction.currency else None,
    }

    return HumanMessage(
        content=[
            {
                "type": "text",
                "text": f"""Validate the extracted invoice data below against the parsed document
text and the available validation tools.

Some values may have been read from images and may therefore be absent from the
parsed text — absence alone is not proof a value is wrong.

EXTRACTED DATA
{extracted_data}

PARSED TEXT
{parsed_text if parsed_text else "No parsed text available for this document."}

For every field decide whether it is correct, correct it when the parsed text or
a tool result explicitly supports a different value, and return the result in the
ValidationReport schema. Remember: bu_name/bu_vat are the CLIENT fields, and
supplier_id/bu_id are always null. Use the validation tools to check both parties.
""",
            }
        ]
    )