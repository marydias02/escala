from pydantic import BaseModel, Field

from email_core.confidence import Confident


class EmailIntent(BaseModel):
    """Why an email that produced no usable PDF might still deserve an action.

    Asked only when an email yielded no PDF — either no attachments at all, or
    attachments that were not PDFs. Two independent questions:

    - was the email trying to DELIVER an accounting document?
    - did it point at that document with a link instead of attaching it?

    Plus the language it is written in, which is what a reply to this email is
    written in (see `decisions.reply_language`) — this email's body is the only
    language evidence there is when no document was read.

    The first question is about delivery, NOT about topic. An email that merely
    mentions an invoice — a satisfaction survey, a payment confirmation, a
    statement — is not delivering one, and the supplier made no mistake to reply
    about. Only a delivery attempt with NO link is a supplier mistake worth a
    reply. A delivery WITH a link is a document we must fetch ourselves, not one
    the supplier forgot to send.
    """

    is_invoice_delivery: Confident[bool] = Field(
        description="""
    True when the email is trying to DELIVER an accounting document (invoice,
    credit note, debit note, receipt) — that is, the body presents itself as
    sending, or having sent, that document.

    Signals that make this True:

    - the body refers to an attached/enclosed invoice, fatura, factura, recibo,
      nota de crédito, nota de débito;
    - the body announces a document being sent ("em anexo", "segue", "attached",
      "please find");
    - the body says the document can be obtained at a link or portal.

    Signals that make this False:

    - general correspondence, questions, scheduling, marketing, newsletters;
    - automated notifications unrelated to a specific document;
    - delivery notes or purchase orders with no accounting document involved;
    - the body NAMES or references an invoice but is not sending it: a
      satisfaction survey about a past invoice, a payment confirmation or
      receipt acknowledgement, an account statement, a reminder, a question
      about a document we already have.

    An invoice number in the body is not by itself a delivery. Ask what the
    email is FOR: if its purpose is anything other than getting the document to
    us, this is False.

    Return False when the body is empty or gives no indication either way.
    """
    )

    has_invoice_link: Confident[bool] = Field(
        description="""
    True when the email points at a document to be downloaded rather than
    attaching it.

    Signals that make this True:

    - a URL the body presents as where the invoice lives (supplier portal,
      billing portal, "consulte a sua fatura em", "download your invoice",
      "acesse aqui", a link to a .pdf);
    - instructions to log into a portal or account to obtain the document.

    Signals that make this False:

    - no URL at all;
    - URLs that are plainly not the document: the sender's homepage, social
      media icons, email-signature links, unsubscribe links, tracking pixels,
      privacy-policy or legal boilerplate links;
    - a link to something that is not the document at all: a feedback or survey
      form, a satisfaction questionnaire, a marketing page.

    Judge what the link is FOR, not whether a link exists. A signature link in
    an otherwise attachment-less invoice email is False.

    Return False when the body is empty.
    """
    )

    language: Confident[str] | None = Field(
        default=None,
        description="""
    The language the email is written in, as a lowercase ISO 639-1 code: 'pt',
    'en', 'es', 'fr', ...

    Judge the body's own wording, not the sender's address or domain.

    Return null for an empty body, or one too short to tell (a bare signature block).
    """,
    )
