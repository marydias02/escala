import base64
from dataclasses import dataclass
from pathlib import Path


@dataclass
class InvoiceDocument:
    """A single, already-split accounting document ready for the pipeline.

    The pipeline starts here: one PDF == one document. Splitting a multi-document
    PDF into these units is the job of the upstream ingestion pipeline.
    """

    filename: str
    path: Path
    encoded_pdf: str

    def as_data_url(self) -> str:
        """The base64 payload in the data-URL form the chat models expect."""
        return f"data:application/pdf;base64,{self.encoded_pdf}"


def load_document(pdf_path: Path) -> InvoiceDocument:
    """Read a single-document PDF from disk and base64-encode it for the LLM."""
    pdf_path = Path(pdf_path)
    pdf_bytes = pdf_path.read_bytes()

    return InvoiceDocument(
        filename=pdf_path.name,
        path=pdf_path,
        encoded_pdf=base64.b64encode(pdf_bytes).decode("utf-8"),
    )