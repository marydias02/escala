from config.settings import settings
from utils.llm_factory import LLMFactory


class ExtractionPipeline:
    def __init__(self, llm_factory: LLMFactory):
        self.llm_factory = llm_factory

    def run(
        self,
    ):
        # Load invoices from Outlook

        # Detect elligible invoices (.pdf extension)

        # Add inelligile invoices to stack of emails to send with reason wrong format type

        # Agent extraction
        # - Include a safeguard that uses a VLM to extract digitalized invoices in PDFs

        # Agent classification
        # - Detect if invoice is:
        # --Receipt
        # --Insurance Warning
        # --Building expense
        # --"Proforma" invoice
        # -- Detect if invoice is a copy or duplicated version
        # -- All the rest is ok

        # Add out-of-scope types of documents to emails to send

        # Perform invoice validations
        # - Base data validation (NIF, Business Unit Name)
        # - Ensure invoice is not duplicated (i.e., there isnt any invoice in SAP with the same reference number)

        # Add invoices that do not pass the first round of validations to emails to send

        # Perform OCR validation
        # -- Read corresponding PO number
        # -- If there isn't any:
        # ---- Submit invoice to processes to validate manually
        # -- Otherwise:
        # ---- If all fields match, proceeds
        # ---- Otherwise, Submit invoice to process it manually

        # Ingest valid invoices in SAP

        # Ingest invoices for manual validation in appropriate table

        # Send all emails to corresponding parties

        pass


def create_pipeline(
    llm_factory: LLMFactory = None,
) -> ExtractionPipeline:
    if llm_factory is None:
        llm_factory = LLMFactory.from_settings(settings)

    return ExtractionPipeline(llm_factory=llm_factory)


if __name__ == "__main__":
    pass
