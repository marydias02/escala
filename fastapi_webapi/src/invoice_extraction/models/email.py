from dataclasses import dataclass, field

from pydantic import BaseModel, Field


@dataclass
class EmailAttachment:
    """One attachment as read off the source message, still in memory."""

    filename: str
    data: bytes

    @property
    def is_pdf(self) -> bool:
        return self.filename.lower().endswith(".pdf")


@dataclass
class LoadedEmail:
    """A parsed email, before anything has been written to disk.

    Produced by the loaders in `invoice_extraction.loading`; consumed by the
    ingestion pipeline, which is what decides where the bytes land.
    """

    sender_email: str
    subject: str
    body: str
    reception_date: str
    attachments: list[EmailAttachment] = field(default_factory=list)
    message_id: str = ""


class EmailContent(BaseModel):
    """The `email_content.json` written next to an email's chunked PDFs.

    `number_annexes` counts every attachment that arrived with the email (pdf,
    csv, png, xlsx, ...). `number_chunked_pdfs` counts only the single-document
    PDFs that segmentation produced from the PDF attachments.
    """

    sender_email: str = Field(description="Address the email was sent from.")
    email_subject: str = Field(description="Subject line of the email.")
    email_content: str = Field(description="Plain-text body of the email.")
    reception_date: str = Field(description="When the email was received, ISO-8601.")
    number_annexes: int = Field(description="Total attachments of any type.")
    number_chunked_pdfs: int = Field(description="Single-document PDFs produced by segmentation.")
    message_id: str = Field(default="", description="Graph message id, for dedup against fct_processes.")
