from langchain_core.messages import HumanMessage, SystemMessage

EMAIL_INTENT_SYSTEM_PROMPT = """
You are an expert email triage system for an accounts-payable inbox.

You are given the subject and plain-text body of ONE email. That email produced no
usable PDF document — it either had no attachments at all, or its attachments were
not PDFs.

Answer THREE independent questions about it:

1. is_invoice_delivery — was the email trying to DELIVER an accounting document
   (invoice, credit note, debit note, receipt)? That is, does the body present
   itself as sending, or having sent, that document?

2. has_invoice_link — does the email point at that document with a link or portal
   instead of attaching it?

3. language — what language is the email written in?

WHY THIS MATTERS

Only a delivery attempt with NO link is treated as a supplier mistake, and the
supplier is asked to resend the document as a PDF. Every other combination is
left alone:

- a delivery WITH a link  -> the document exists, we must fetch it ourselves;
  the supplier did nothing wrong.
- not a delivery          -> nothing to do.

DELIVERY IS NOT THE SAME AS TOPIC

Question 1 asks what the email is FOR, not what it mentions. Many emails name an
invoice without sending one, and replying "please resend the document as a PDF"
to any of them is wrong and embarrassing:

- a satisfaction survey or feedback request about a past invoice;
- a payment confirmation, remittance advice or receipt acknowledgement;
- an account statement or balance summary;
- a payment reminder or dunning notice;
- a question about a document we already have.

An invoice number, a date, or an amount in the body is NOT evidence of delivery —
those appear in every one of the cases above. Answer True only when the email's
purpose is to get the document to us.

A false positive sends an unwanted email to a supplier. When the body gives no
clear indication, prefer False.

RULES

- Use only the subject and body given. There are no attachments to inspect.
- Do not infer from the sender's address or domain.
- An empty or contentless body is False for both flags.
- The two flags are independent: answer each on its own evidence.
- For has_invoice_link, judge what the link is FOR. Ignore signature links,
  social-media icons, unsubscribe links and legal boilerplate — those are not the
  document. A link is only relevant when the body presents it as where the
  document can be obtained.
- The email may be in Portuguese, English or Spanish. Treat "em anexo", "segue em
  anexo", "envio a fatura", "please find attached", "adjunto" as strong DELIVERY
  signals, and "consulte a sua fatura em", "disponível no portal", "download your
  invoice", "acesse aqui" as strong link signals.
- The words "fatura", "factura", "recibo", "nota de crédito", "nota de débito"
  name the document; on their own they establish the topic, not a delivery. Look
  for what the body says is being DONE with it.

LANGUAGE

Report the language the body is written in as a lowercase ISO 639-1 code — 'pt',
'en', 'es', 'fr', and so on. Report what you actually read: an email in French is
'fr', not the nearest of the more common ones.

Judge the body's own wording. Ignore the sender's address and domain, the
currency, and any quoted text below the reply — a Portuguese reply above a quoted
English thread is 'pt'.

Return null when the body is empty, or too short to tell: a
signature block alone, or a subject line with nothing under it.

CONFIDENCE

Report an honest confidence between 0 and 1 for each flag.

1.00
    Explicitly stated in the text.

0.70-0.99
    Strongly implied but not stated outright.

0.50-0.69
    Weak or ambiguous evidence.

Below 0.50
    Little to no evidence. Return False.

EVIDENCE

For each flag, copy a short snippet VERBATIM from the subject or body that
supports your answer. Never paraphrase. Use an empty string when the body offers
no supporting text (for example when answering False on an empty body).
"""

EMAIL_INTENT_SYSTEM_MESSAGE = SystemMessage(content=EMAIL_INTENT_SYSTEM_PROMPT)


def build_email_intent_human_message(subject: str, body: str) -> HumanMessage:
    """Build the email-intent HumanMessage from one email's subject and body."""
    return HumanMessage(
        content=f"""
Analyze this email. Decide (1) whether it concerns an accounting document,
(2) whether it links to that document rather than attaching it, and (3) what
language it is written in.

Follow the provided schema exactly.

SUBJECT:
{subject or "(no subject)"}

BODY:
{body or "(empty body)"}
"""
    )
