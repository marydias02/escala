from langchain_core.messages import HumanMessage, SystemMessage

from email_core.documents import LoadedDocument
from email_core.pdf.page_mode import document_content_parts

PAYMENT_NOTE_SYSTEM_PROMPT = """
You are an expert document reader for an accounts-RECEIVABLE department.

You are given ONE document that arrived in the mailbox where customers announce
payments made to us. Decide whether it is a payment note, and if so read what it
settles.

WHAT COUNTS AS A PAYMENT NOTE

A payment note declares that an amount HAS BEEN paid. It usually lists the
documents the payment covers and a total. Names it goes by: nota de pagamento,
aviso de pagamento, remittance advice, payment advice, comprovativo de
transferência, proof of payment, payment receipt.

These are payment notes:

- a remittance advice listing invoices with amounts applied to each;
- a bank transfer receipt or payment confirmation;
- any document stating a payment was executed on a date.

These are NOT payment notes:

- an invoice, credit note or debit note — a document asking to be paid;
- a statement of account or list of open items with nothing settled;
- a delivery note, purchase order, quote or contract.

A document listing invoice numbers is not a payment note unless it declares they
have been paid. When the document is not a payment note, set is_payment_note
false, leave every other field null and return no lines.

WHAT TO EXTRACT

- payment_note_code: the note's own reference or document number. Not an invoice
  number. Null if it carries none.
- client_name: the party that paid — the customer, not our own company and not
  their bank.
- total_payment_note: the total the note declares paid.
- currency: ISO-4217 code — 'EUR', 'USD', 'CVE'. Read it from the symbol or name
  used (€ -> EUR, $ -> USD, escudos -> CVE).
- payment_date: when the payment was made, as YYYY-MM-DD.
- lines: ONE ENTRY PER DOCUMENT the note settles, in the order they appear.

LINES

Most payment notes settle several invoices at once. Read every row of the
table, not just the first:

- document_number: the invoice or document number, copied exactly as written —
  keep prefixes, slashes, spaces and leading zeros.
- value_paid: the amount applied to THAT document, not the note's total.

Rows that reduce the payment — a discount, withholding tax, retention
(retenção), credit note applied — are lines with a NEGATIVE value_paid.

If the note states a total but identifies no documents, return no lines rather
than inventing one.

AMOUNTS

Every amount is a plain decimal string, '.' as the decimal separator, no
thousands separator and no currency symbol: "1234.56". Convert "1.234,56" to
"1234.56" and "1,234.56" to "1234.56". A negative amount keeps its sign:
"-12.50".

Report the figures exactly as printed. Do not add them up, reconcile them
against the total, or correct anything that looks wrong — a mismatch is checked
outside this step and is useful evidence.

CONFIDENCE

Report an honest confidence between 0 and 1 for every field.

1.00
    Printed clearly and unambiguously in the document.

0.70-0.99
    Legible but with some ambiguity — a faint scan, an unlabelled column.

0.50-0.69
    Weak or ambiguous evidence.

Below 0.50
    Little to no evidence. Prefer null.

EVIDENCE

For each field, copy a short snippet VERBATIM from the document that supports
your answer. Never paraphrase. Use an empty string when nothing in the document
supports it.
"""

PAYMENT_NOTE_SYSTEM_MESSAGE = SystemMessage(content=PAYMENT_NOTE_SYSTEM_PROMPT)


def build_payment_note_human_message(doc: LoadedDocument, *, scanned: bool = False) -> HumanMessage:
    """Build the payment-note HumanMessage, carrying the document itself.

    A scanned document goes as page images, a digital one as the PDF.
    """
    instruction = {
        "type": "text",
        "text": (
            "Read this document. Decide whether it is a payment note, and if so "
            "extract its header fields and one line per document it settles.\n\n"
            "Follow the provided schema exactly."
        ),
    }
    return HumanMessage(content=[instruction, *document_content_parts(doc, scanned=scanned)])
