"""Commonly used column meanings for SAP tables replicated to the lakehouse.

Each table has a `<TABLE>_TABLE_DESCRIPTION` string (what the table is) and a
`<TABLE>_COLUMN_DESCRIPTIONS` dict (column name -> plain-language meaning). The
`SAPTableMetadata` model at the bottom wraps both behind a single `table_name`.
"""

import re
from collections import Counter

from pydantic import BaseModel, field_validator

ACDOCA_TABLE_DESCRIPTION: str = (
    "Universal Journal line items (S/4HANA). One row per posting line, storing financial "
    "accounting, controlling, margin analysis and (when active) material ledger data in a "
    "single table. It is the single source of truth for the general ledger: every FI/CO "
    "document flows here, replacing the classic GLT0/FAGLFLEXA/COEP totals and line tables."
)

ACDOCA_COLUMN_DESCRIPTIONS: dict[str, str] = {
    # Client / keys
    "RCLNT": "Client",
    "RLDNR": "Ledger",
    "RBUKRS": "Company code",
    "GJAHR": "Fiscal year",
    "BELNR": "Accounting document number",
    "DOCLN": "Journal entry item (universal journal line ID)",
    "BUZEI": "Posting line number within the accounting document",
    # Document header
    "BLART": "Document type",
    "BSCHL": "Posting key",
    "BUDAT": "Posting date",
    "BLDAT": "Document date",
    "CPUDT": "Entry date (date the document was created in the system)",
    "CPUTM": "Entry time",
    "USNAM": "User name who created the document",
    "XBLNR": "Reference document number",
    "AWTYP": "Reference procedure (business transaction that generated the entry, e.g. RMRP for invoices)",
    "AWKEY": "Reference key linking back to the source document (e.g. invoice/MM document number + fiscal year)",
    "AWORG": "Reference organizational unit",
    "SGTXT": "Item text",
    "ZUONR": "Assignment field, often used for open item clearing/matching",
    "SHKZG": "Debit/credit indicator ('S' = debit, 'H' = credit)",
    "POPER": "Posting period",
    "PERIV": "Fiscal year variant",
    "VORGN": "Business transaction type",
    # Amounts / currencies
    "TSL": "Amount in transaction (document) currency",
    "HSL": "Amount in company code (local) currency",
    "KSL": "Amount in group/global currency",
    "OSL": "Amount in hard/freely-defined second local currency",
    "RTCUR": "Transaction currency key",
    "RHCUR": "Company code (local) currency key",
    "RKCUR": "Group currency key",
    "MSL": "Quantity",
    "MEINH": "Base unit of measure",
    # G/L account & organizational assignments
    "RACCT": "G/L account number",
    "KTOSL": "Transaction key (determines automatic G/L account posting)",
    "RCNTR": "Cost center",
    "PRCTR": "Profit center",
    "SEGMENT": "Segment (for segment reporting, e.g. IFRS 8)",
    "GSBER": "Business area",
    "KOKRS": "Controlling area",
    "FUNC_AREA": "Functional area",
    "WERKS": "Plant",
    "MATNR": "Material number",
    "AUFNR": "Order number (internal order)",
    "PS_PSP_PNR": "WBS element (project structure)",
    # Business partners
    "KUNNR": "Customer number",
    "LIFNR": "Vendor number",
    "VBUND": "Trading partner company (for intercompany elimination)",
    "RASSC": "Trading partner / affiliated company (consolidation)",
}

BSAD_TABLE_DESCRIPTION: str = (
    "Accounting: secondary index for customers, cleared items. Contains one row per "
    "customer (account type 'D') open item that has since been cleared, copied from the "
    "accounting document segment for fast access by customer, company code and clearing "
    "date. Used for accounts-receivable analysis, DSO and payment-history reporting. "
    "Open (not yet cleared) customer items live in the sister table BSID."
)

BSAD_COLUMN_DESCRIPTIONS: dict[str, str] = {
    # Client / keys
    "MANDT": "Client",
    "BUKRS": "Company code",
    "KUNNR": "Customer number",
    "UMSKS": "Special G/L transaction type",
    "UMSKZ": "Special G/L indicator",
    "AUGDT": "Clearing date",
    "AUGGJ": "Fiscal year of the clearing document",
    "AUGBL": "Clearing document number",
    "ZUONR": "Assignment number (open item clearing/matching)",
    "GJAHR": "Fiscal year",
    "BELNR": "Accounting document number",
    "BUZEI": "Line item number within the accounting document",
    # Document header
    "BLART": "Document type",
    "BSCHL": "Posting key",
    "SHKZG": "Debit/credit indicator ('S' = debit, 'H' = credit)",
    "BUDAT": "Posting date",
    "BLDAT": "Document date",
    "CPUDT": "Entry date (date the document was created in the system)",
    "WAERS": "Currency key of the document",
    "XBLNR": "Reference document number",
    "MONAT": "Fiscal period",
    "BSTAT": "Document status",
    "GSBER": "Business area",
    "SGTXT": "Item text",
    # Amounts / currencies
    "DMBTR": "Amount in local currency",
    "WRBTR": "Amount in document currency",
    "DMBE2": "Amount in second local currency",
    "DMBE3": "Amount in third local currency",
    "MWSKZ": "Tax code",
    "MWSTS": "Tax amount in local currency",
    "WMWST": "Tax amount in document currency",
    "SKFBT": "Amount eligible for cash discount in document currency",
    "SKNTO": "Cash discount amount in local currency",
    "WSKTO": "Cash discount amount in document currency",
    "NEBTR": "Net payment amount",
    # Payment terms / dunning
    "ZFBDT": "Baseline date for due date calculation",
    "ZTERM": "Terms of payment key",
    "ZBD1T": "Cash discount days 1",
    "ZBD2T": "Cash discount days 2",
    "ZBD3T": "Net payment terms period (days)",
    "ZBD1P": "Cash discount percentage 1",
    "ZBD2P": "Cash discount percentage 2",
    "ZLSCH": "Payment method",
    "ZLSPR": "Payment block key",
    "HBKID": "Short key for the house bank",
    "BVTYP": "Partner bank type",
    "XZAHL": "Indicator: posting key used in a payment transaction",
    "MADAT": "Date of last dunning notice",
    "MANST": "Dunning level",
    "MABER": "Dunning area",
    # Invoice reference (partial payments / credit memos)
    "REBZG": "Number of the invoice the transaction belongs to",
    "REBZJ": "Fiscal year of the relevant invoice (for credit memo)",
    "REBZZ": "Line item in the relevant invoice",
    "REBZT": "Follow-on document type",
    # Organizational assignments
    "HKONT": "G/L account number (general ledger)",
    "SAKNR": "G/L account number",
    "KOSTL": "Cost center",
    "AUFNR": "Order number (internal order)",
    "PROJK": "WBS element (work breakdown structure)",
    "KKBER": "Credit control area",
    "FILKD": "Account number of the branch (head office/branch)",
    # Sales / billing links
    "VBELN": "Billing document (SD)",
    "VBEL2": "Sales document number",
    "POSN2": "Sales document item",
    # Business partner reference keys
    "XREF1": "Business partner reference key 1",
    "XREF2": "Business partner reference key 2",
    "XREF3": "Reference key for line item",
}

BSEG_TABLE_DESCRIPTION: str = (
    "Accounting document segment: the line items of every FI document. One row per "
    "posting line, keyed by company code, document number, fiscal year and line number "
    "(BUKRS/BELNR/GJAHR/BUZEI), with the header stored in BKPF. Holds the account "
    "assignment, debit/credit indicator, amounts in up to three currencies, tax, payment "
    "terms, dunning and clearing information for customer, vendor, G/L and asset lines."
)

BSEG_COLUMN_DESCRIPTIONS: dict[str, str] = {
    # Client / keys
    "MANDT": "Client",
    "BUKRS": "Company code",
    "BELNR": "Accounting document number",
    "GJAHR": "Fiscal year",
    "BUZEI": "Line item number within the accounting document",
    # Line item classification
    "BUZID": "Identification of the line item (origin, e.g. tax, cash discount)",
    "AUGDT": "Clearing date",
    "AUGCP": "Clearing entry date",
    "AUGBL": "Clearing document number",
    "AUGGJ": "Fiscal year of the clearing document",
    "BSCHL": "Posting key",
    "KOART": "Account type ('D' = customer, 'K' = vendor, 'S' = G/L, 'A' = asset, 'M' = material)",
    "UMSKZ": "Special G/L indicator",
    "UMSKS": "Special G/L transaction type",
    "SHKZG": "Debit/credit indicator ('S' = debit, 'H' = credit)",
    "XBILK": "Indicator: account is a balance sheet account",
    "GVTYP": "P&L statement account type",
    # Document header fields (copied from the header onto each line)
    "H_BLART": "Document type (e.g. 'DZ' customer payment, 'DA' customer document in SAP standard)",
    "H_BLDAT": "Document date (date of the original document, e.g. the invoice date)",
    "H_BUDAT": "Posting date",
    "H_WAERS": "Currency key of the document",
    # Amounts / currencies
    "DMBTR": "Amount in local currency",
    "WRBTR": "Amount in document currency",
    "DMBE2": "Amount in second local currency",
    "DMBE3": "Amount in third local currency",
    "PSWBT": "Amount for updating in general ledger (transaction currency)",
    "PSWSL": "Update currency for general ledger transaction figures",
    "MWSKZ": "Tax code",
    "MWSTS": "Tax amount in local currency",
    "WMWST": "Tax amount in document currency",
    "HWBAS": "Tax base amount in local currency",
    "FWBAS": "Tax base amount in document currency",
    "KTOSL": "Transaction key (determines automatic G/L account posting)",
    "SKFBT": "Amount eligible for cash discount in document currency",
    "SKNTO": "Cash discount amount in local currency",
    "WSKTO": "Cash discount amount in document currency",
    # Account assignments
    "HKONT": "G/L account number (general ledger)",
    "SAKNR": "G/L account number",
    "KUNNR": "Customer number",
    "LIFNR": "Vendor number",
    "FILKD": "Account number of the branch (head office/branch)",
    "GSBER": "Business area",
    "PARGB": "Trading partner business area",
    "KOSTL": "Cost center",
    "AUFNR": "Order number (internal order)",
    "PROJK": "WBS element (work breakdown structure)",
    "PRCTR": "Profit center",
    "SEGMENT": "Segment for segment reporting",
    "KOKRS": "Controlling area",
    "PS_PSP_PNR": "WBS element (project structure)",
    "MATNR": "Material number",
    "WERKS": "Plant",
    "MENGE": "Quantity",
    "MEINS": "Base unit of measure",
    "VBUND": "Trading partner company (for intercompany elimination)",
    # Payment terms / dunning
    "ZFBDT": "Baseline date for due date calculation",
    "ZTERM": "Terms of payment key",
    "ZBD1T": "Cash discount days 1",
    "ZBD2T": "Cash discount days 2",
    "ZBD3T": "Net payment terms period (days)",
    "ZBD1P": "Cash discount percentage 1",
    "ZBD2P": "Cash discount percentage 2",
    "ZLSCH": "Payment method",
    "ZLSPR": "Payment block key",
    "HBKID": "Short key for the house bank",
    "BVTYP": "Partner bank type",
    "XZAHL": "Indicator: posting key used in a payment transaction",
    "MADAT": "Date of last dunning notice",
    "MANST": "Dunning level",
    "MABER": "Dunning area",
    "MSCHL": "Dunning key",
    "MANSP": "Dunning block",
    # Invoice reference (partial payments / credit memos)
    "REBZG": "Number of the invoice the transaction belongs to",
    "REBZJ": "Fiscal year of the relevant invoice (for credit memo)",
    "REBZZ": "Line item in the relevant invoice",
    "REBZT": "Follow-on document type",
    # Reference / origin
    "XREF1": "Business partner reference key 1",
    "XREF2": "Business partner reference key 2",
    "XREF3": "Reference key for line item",
    "ZUONR": "Assignment number (open item clearing/matching)",
    "SGTXT": "Item text",
    "XBLNR": "Reference document number",
    "VBEL2": "Sales document number",
    "POSN2": "Sales document item",
    "VBELN": "Billing document (SD)",
    "EBELN": "Purchasing document number",
    "EBELP": "Purchasing document item",
    "ZEKKN": "Sequential number of account assignment (purchasing)",
}

BUT000_TABLE_DESCRIPTION: str = (
    "Business Partner: central data (general data at client level). One row per business "
    "partner, holding the partner category (person / organization / group), name, "
    "grouping, search terms, communication language and central block/deletion flags. "
    "It is the hub of the SAP Business Partner model; customer- and vendor-specific "
    "attributes hang off it via KNA1/LFA1 and the CVI mapping tables."
)

BUT000_COLUMN_DESCRIPTIONS: dict[str, str] = {
    # Keys / category
    "CLIENT": "Client",
    "PARTNER": "Business partner number",
    "TYPE": "Business partner category (1 = Person, 2 = Organization, 3 = Group)",
    "BPKIND": "Business partner grouping",
    "BU_GROUP": "Business partner grouping (alternate/legacy field)",
    "PARTNER_GUID": "Business partner GUID",
    # Status flags
    "XBLCK": "Central block indicator (business partner blocked centrally)",
    "XDELE": "Central deletion flag",
    # Organization data (TYPE = 2)
    "NAME_ORG1": "Organization name, line 1",
    "NAME_ORG2": "Organization name, line 2",
    "NAME_ORG3": "Organization name, line 3",
    "NAME_ORG4": "Organization name, line 4",
    "LEGALORG": "Legal form of the organization",
    # Person data (TYPE = 1)
    "TITLE": "Form-of-address key",
    "TITLE_LET": "Form-of-address text used in letters",
    "NAME_FIRST": "First name",
    "NAME_LAST": "Last name",
    "NAME_LAST2": "Second last name",
    "NAMEMIDDLE": "Middle name",
    "BIRTHPL": "Place of birth",
    "BIRTHDT": "Date of birth",
    "DEATHDT": "Date of death",
    "NATPERSON": "Indicator: natural person (vs. legal entity)",
    # Group data (TYPE = 3)
    "NAME_GRP1": "Group name, line 1",
    "NAME_GRP2": "Group name, line 2",
    # Search / communication
    "BU_SORT1": "Search term 1 (used for matching/lookup)",
    "BU_SORT2": "Search term 2 (used for matching/lookup)",
    "LANGU": "Communication language",
    "LANGU_CORR": "Correspondence language",
    "ADDRCOMM": "Address number for communication data",
    # Audit
    "CREATEDON": "Date the business partner was created",
    "CREATEDBY": "User who created the business partner",
    "CHANGEDON": "Date of the last change",
    "CHANGEDBY": "User who made the last change",
}

CEPCT_TABLE_DESCRIPTION: str = (
    "Texts for profit center master data. One row per profit center, controlling area, "
    "validity period and language, providing the short and long descriptions shown for a "
    "profit center. The master data itself is in CEPC; join on KOKRS/PRCTR/DATBI to "
    "resolve a profit center code to a human-readable name."
)

CEPCT_COLUMN_DESCRIPTIONS: dict[str, str] = {
    # Keys
    "MANDT": "Client",
    "SPRAS": "Language key of the text",
    "PRCTR": "Profit center",
    "DATBI": "Valid-to date (end of validity period)",
    "KOKRS": "Controlling area",
    "KDATB": "Valid-from date (start of validity period)",
    # Texts
    "KTEXT": "Short text / medium description of the profit center",
    "LTEXT": "Long text / long description of the profit center",
    "MCTXT": "Search text (uppercase, for matchcode lookup)",
}

EKKO_TABLE_DESCRIPTION: str = (
    "Purchasing document header. One row per purchasing document (purchase order, "
    "request for quotation, outline agreement/contract or scheduling agreement), keyed "
    "by document number (EBELN). Holds the vendor, purchasing organization and group, "
    "document type and category, currency and exchange rate, payment and delivery terms "
    "and the release (approval) strategy. Line-level detail is in EKPO."
)

EKKO_COLUMN_DESCRIPTIONS: dict[str, str] = {
    # Keys
    "MANDT": "Client",
    "EBELN": "Purchasing document number",
    "BUKRS": "Company code",
    "BSTYP": "Purchasing document category (F = order, A = RFQ, K = contract, L = scheduling agreement)",
    "BSART": "Purchasing document type",
    "BSAKZ": "Control indicator for purchasing document type",
    "STATU": "Status of the purchasing document (RFQ/quotation)",
    "LOEKZ": "Deletion indicator in purchasing document header",
    # Dates / audit
    "AEDAT": "Date the purchasing document was created / changed",
    "ERNAM": "Name of the person who created the purchasing document",
    "BEDAT": "Purchasing document date",
    "KDATB": "Start of validity period",
    "KDATE": "End of validity period",
    # Partners / organization
    "LIFNR": "Vendor account number",
    "EKORG": "Purchasing organization",
    "EKGRP": "Purchasing group",
    "LLIEF": "Supplying vendor (if different from ordering vendor)",
    "RESWK": "Supplying (issuing) plant in stock transport order",
    "KUNNR": "Customer number (for third-party / returns)",
    "VERKF": "Responsible salesperson at the vendor",
    "TELF1": "Vendor's telephone number",
    # Currency / terms
    "WAERS": "Currency key",
    "WKURS": "Exchange rate",
    "KUFIX": "Indicator: exchange rate is fixed",
    "ZTERM": "Terms of payment key",
    "ZBD1T": "Cash discount days 1",
    "ZBD2T": "Cash discount days 2",
    "ZBD3T": "Net payment terms period (days)",
    "ZBD1P": "Cash discount percentage 1",
    "ZBD2P": "Cash discount percentage 2",
    "INCO1": "Incoterms (part 1)",
    "INCO2": "Incoterms (part 2, location)",
    # Amounts / totals
    "KTWRT": "Target value of the contract / total value (document currency)",
    "RLWRT": "Total value released against contract",
    "FRGGR": "Release group (release strategy)",
    "FRGSX": "Release strategy",
    "FRGKE": "Release indicator (purchasing document released?)",
    "FRGZU": "Release status (which release codes have been effected)",
    "FRGRL": "Release not yet completely effected",
    "MEMORY": "Indicator: purchasing document held / incomplete",
    # References
    "ANGNR": "Quotation number in vendor's system",
    "IHRAN": "Vendor quotation date",
    "VERKF_TEXT": "Vendor sales-representative name (free text)",
    "LANDS": "Country of the tax-relevant destination",
}

EKPO_TABLE_DESCRIPTION: str = (
    "Purchasing document item. One row per line of a purchasing document, keyed by "
    "document number and item number (EBELN/EBELP), with the header in EKKO. Holds the "
    "material or free-text description, plant and storage location, ordered quantity and "
    "units, net price and value, tax code, account assignment category, and the goods-"
    "receipt / invoice-receipt control flags used by logistics invoice verification."
)

EKPO_COLUMN_DESCRIPTIONS: dict[str, str] = {
    # Keys
    "MANDT": "Client",
    "EBELN": "Purchasing document number",
    "EBELP": "Purchasing document item number",
    "LOEKZ": "Deletion / blocking indicator for the item",
    "STATU": "RFQ status",
    "AEDAT": "Date the item was last changed",
    # Material / description
    "TXZ01": "Short text (description) of the item",
    "MATNR": "Material number",
    "EMATN": "Material number for which the conditions apply",
    "BUKRS": "Company code",
    "WERKS": "Plant",
    "LGORT": "Storage location",
    "MATKL": "Material group",
    "INFNR": "Purchasing info record number",
    "IDNLF": "Vendor's material number",
    # Quantities / units
    "MENGE": "Purchase order quantity",
    "MEINS": "Order unit of measure",
    "BPRME": "Order price unit of measure",
    "BPUMZ": "Numerator for conversion of order price unit to order unit",
    "BPUMN": "Denominator for conversion of order price unit to order unit",
    "UMREZ": "Numerator for conversion of order unit to base unit",
    "UMREN": "Denominator for conversion of order unit to base unit",
    # Prices / values
    "NETPR": "Net price in the purchasing document (document currency)",
    "PEINH": "Price unit (quantity the net price refers to)",
    "NETWR": "Net order value in document currency",
    "BRTWR": "Gross order value in document currency",
    "EFFWR": "Effective value of the item",
    "MWSKZ": "Tax code",
    "BONBA": "Rebate basis 1",
    # Delivery / control
    "ELIKZ": "Delivery completed indicator",
    "EREKZ": "Final invoice indicator",
    "PSTYP": "Item category in the purchasing document",
    "KNTTP": "Account assignment category",
    "WEPOS": "Goods receipt indicator",
    "WEUNB": "Goods receipt, non-valuated",
    "REPOS": "Invoice receipt indicator",
    "WEBRE": "Indicator: GR-based invoice verification",
    "KZABS": "Confirmation required indicator",
    "PLIFZ": "Planned delivery time in days",
    "PRDAT": "Date of the price determination",
    "NETLR": "Value of delivered but not yet invoiced goods",
    # Account assignment references
    "KONNR": "Number of the referenced outline agreement (contract)",
    "KTPNR": "Item number of the referenced outline agreement",
    "ANFNR": "RFQ number the item refers to",
    "ANFPS": "RFQ item number the item refers to",
    "BANFN": "Purchase requisition number",
    "BNFPO": "Purchase requisition item number",
    "SAKTO": "G/L account number for the item",
    "KOSTL": "Cost center for the item",
    "AUFNR": "Order number for the item",
    "PS_PSP_PNR": "WBS element for the item",
    "MATNR_EXTERNAL": "Long material number (external format)",
}

LFA1_TABLE_DESCRIPTION: str = (
    "Vendor master (general section). One row per vendor/supplier account, keyed by the "
    "vendor number (LIFNR), holding the name, address, communication data, tax and VAT "
    "registration numbers, account group, and central posting/purchasing/payment block and "
    "deletion flags. Company-code data is in LFB1 and purchasing-organization data in LFM1; "
    "join to EKKO/BSEG on LIFNR to label a vendor. The EU VAT id is in STCEG and the "
    "domestic tax id in STCD1."
)

LFA1_COLUMN_DESCRIPTIONS: dict[str, str] = {
    # Keys
    "MANDT": "Client",
    "LIFNR": "Vendor account number",
    "ADRNR": "Address number (link to the central address management)",
    # Names
    "NAME1": "Vendor name, line 1",
    "NAME2": "Vendor name, line 2",
    "NAME3": "Vendor name, line 3",
    "NAME4": "Vendor name, line 4",
    "ANRED": "Title / form of address",
    "SORTL": "Sort field (search term)",
    "MCOD1": "Search term for matchcode use (uppercase name 1)",
    "MCOD2": "Search term for matchcode use (uppercase name 2)",
    "MCOD3": "Search term for matchcode use (uppercase city)",
    # Address
    "STRAS": "Street and house number",
    "ORT01": "City",
    "ORT02": "District",
    "PSTLZ": "Postal code",
    "LAND1": "Country key",
    "REGIO": "Region (state, province, county)",
    "PFACH": "PO box",
    "PSTL2": "PO box postal code",
    "PFORT": "PO box city",
    "LZONE": "Transportation zone to or from which goods are delivered",
    "TXJCD": "Tax jurisdiction code",
    "SPRAS": "Language key",
    # Communication
    "TELF1": "First telephone number",
    "TELF2": "Second telephone number",
    "TELFX": "Fax number",
    # Tax / VAT
    "STCEG": "VAT registration number (EU VAT id)",
    "STCD1": "Tax number 1 (domestic/national tax id, used when the vendor has no EU VAT id)",
    "STCD2": "Tax number 2",
    "STCD3": "Tax number 3",
    "STCD4": "Tax number 4",
    "STCDT": "Tax number type",
    "STKZU": "Indicator: vendor is liable for VAT",
    "STKZN": "Indicator: natural person (vs. legal entity)",
    "FISKN": "Account number of the master record with the fiscal address",
    "FITYP": "Tax type",
    # Classification
    "KTOKK": "Vendor account group",
    "BRSCH": "Industry key",
    "KONZS": "Group key (links vendors belonging to the same corporate group)",
    "BEGRU": "Authorization group",
    "XCPDK": "Indicator: one-time account (vendor data is entered per document)",
    "VBUND": "Company ID of trading partner (for intercompany elimination)",
    "KUNNR": "Customer number (when the vendor is also a customer)",
    "WERKS": "Plant",
    # Blocks / status
    "SPERR": "Central posting block",
    "SPERM": "Centrally imposed purchasing block",
    "SPERZ": "Payment block",
    "SPERQ": "Function that will be blocked",
    "LOEVM": "Central deletion flag for the master record",
    "NODEL": "Central deletion block for the master record",
    # Audit
    "ERDAT": "Date the vendor record was created",
    "ERNAM": "User who created the vendor record",
}

SKAT_TABLE_DESCRIPTION: str = (
    "G/L account master record: chart-of-accounts area, descriptions. One row per chart "
    "of accounts, G/L account and language, providing the account's short (20-char) and "
    "long (50-char) text. The chart-of-accounts level data is in SKA1 and the company-"
    "code level data in SKB1; join on KTOPL/SAKNR to label a G/L account number."
)

SKAT_COLUMN_DESCRIPTIONS: dict[str, str] = {
    # Keys
    "MANDT": "Client",
    "SPRAS": "Language key of the text",
    "KTOPL": "Chart of accounts",
    "SAKNR": "G/L account number",
    # Texts
    "TXT20": "G/L account short text (20 characters)",
    "TXT50": "G/L account long text (50 characters)",
    "MCOD1": "Search term for matchcode use (uppercase short text)",
}

T001_TABLE_DESCRIPTION: str = (
    "Company codes. One row per company code, the smallest organizational unit for which "
    "a complete, self-contained set of accounts can be drawn up, keyed by BUKRS. Holds the "
    "company name, city and country, local currency, language, chart of accounts, fiscal "
    "year variant and posting-period variant, and the company's own VAT registration "
    "number. Referenced as BUKRS by EKKO, EKPO, BSEG, BSAD and the other accounting tables."
)

T001_COLUMN_DESCRIPTIONS: dict[str, str] = {
    # Keys
    "MANDT": "Client",
    "BUKRS": "Company code",
    "RCOMP": "Company (trading partner ID used for consolidation)",
    "ADRNR": "Address number (link to the central address management)",
    # Name / address
    "BUTXT": "Name of the company code or company",
    "ORT01": "City",
    "LAND1": "Country key",
    "SPRAS": "Language key",
    "TXJCD": "Tax jurisdiction code",
    # Currency / accounting settings
    "WAERS": "Currency key (company code / local currency)",
    "WAABW": "Maximum exchange rate deviation in percent",
    "KTOPL": "Chart of accounts",
    "PERIV": "Fiscal year variant",
    "OPVAR": "Posting period variant",
    "FSTVA": "Field status variant",
    "XMWSN": "Indicator: calculate tax on net amount",
    "XNEGP": "Indicator: negative postings allowed",
    # Controlling / credit management
    "KOKFI": "Allocation indicator for company code to controlling area",
    "FIKRS": "Financial management area",
    "KKBER": "Credit control area",
    # Tax
    "STCEG": "VAT registration number of the company code",
}


# --- Registry -------------------------------------------------------------------

TABLE_DESCRIPTIONS: dict[str, str] = {
    "ACDOCA": ACDOCA_TABLE_DESCRIPTION,
    "BSAD": BSAD_TABLE_DESCRIPTION,
    "BSEG": BSEG_TABLE_DESCRIPTION,
    "BUT000": BUT000_TABLE_DESCRIPTION,
    "CEPCT": CEPCT_TABLE_DESCRIPTION,
    "EKKO": EKKO_TABLE_DESCRIPTION,
    "EKPO": EKPO_TABLE_DESCRIPTION,
    "LFA1": LFA1_TABLE_DESCRIPTION,
    "SKAT": SKAT_TABLE_DESCRIPTION,
    "T001": T001_TABLE_DESCRIPTION,
}

COLUMN_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "ACDOCA": ACDOCA_COLUMN_DESCRIPTIONS,
    "BSAD": BSAD_COLUMN_DESCRIPTIONS,
    "BSEG": BSEG_COLUMN_DESCRIPTIONS,
    "BUT000": BUT000_COLUMN_DESCRIPTIONS,
    "CEPCT": CEPCT_COLUMN_DESCRIPTIONS,
    "EKKO": EKKO_COLUMN_DESCRIPTIONS,
    "EKPO": EKPO_COLUMN_DESCRIPTIONS,
    "LFA1": LFA1_COLUMN_DESCRIPTIONS,
    "SKAT": SKAT_COLUMN_DESCRIPTIONS,
    "T001": T001_COLUMN_DESCRIPTIONS,
}

#: Tables that have both a description and column mappings defined here.
DOCUMENTED_TABLES: tuple[str, ...] = tuple(TABLE_DESCRIPTIONS)


def readable_column_name(description: str) -> str:
    """A column description as snake_case: lower-case, words joined by '_'.

    Parenthetical asides ("(general ledger)", "('S' = debit, 'H' = credit)") are
    dropped, and single-letter abbreviations are closed up ("G/L" -> "gl"), so
    "Customer number" -> "customer_number" and "G/L account number (general
    ledger)" -> "gl_account_number".
    """
    text = re.sub(r"\([^)]*\)", "", description)
    text = re.sub(r"\b([A-Za-z])[/&]([A-Za-z])\b", r"\1\2", text)
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


class SAPTableMetadata(BaseModel):
    """Human-readable metadata for one SAP table replicated to the lakehouse.

    Declare it with just the table name and read back the table's meaning or its
    documented columns::

        meta = SAPTableMetadata(table_name="ACDOCA")
        meta.description  # -> "Universal Journal line items (S/4HANA). ..."
        meta.columns["RACCT"]  # -> "G/L account number"
        meta.column_meaning("racct")  # -> "G/L account number" (case-insensitive)
        meta.readable_column_names["RACCT"]  # -> "gl_account_number"
        print(meta.describe())  # description + full column list, ready for a prompt

    `table_name` is normalized to upper case and must be one of
    `DOCUMENTED_TABLES`; anything else raises a `ValidationError`.
    """

    table_name: str

    model_config = {"frozen": True}

    @field_validator("table_name", mode="before")
    @classmethod
    def _normalize_and_check(cls, value: str) -> str:
        if not isinstance(value, str):
            raise TypeError("table_name must be a string")
        name = value.strip().upper()
        if name not in TABLE_DESCRIPTIONS:
            available = ", ".join(DOCUMENTED_TABLES)
            raise ValueError(f"Unknown SAP table '{value}'. Documented tables: {available}")
        return name

    @property
    def description(self) -> str:
        """One-paragraph explanation of what the table holds."""
        return TABLE_DESCRIPTIONS[self.table_name]

    @property
    def columns(self) -> dict[str, str]:
        """Mapping of documented column name -> plain-language meaning.

        A copy, so callers can mutate it freely; not every physical column of the
        table is present, only the ones worth documenting.
        """
        return dict(COLUMN_DESCRIPTIONS[self.table_name])

    @property
    def column_names(self) -> list[str]:
        """The documented column names, in declaration order."""
        return list(COLUMN_DESCRIPTIONS[self.table_name])

    @property
    def readable_column_names(self) -> dict[str, str]:
        """Documented SAP column name -> snake_case name derived from its meaning.

        E.g. BSEG "KUNNR" -> "customer_number". Columns whose meanings reduce to
        the same name (BSEG `HKONT` and `SAKNR` are both "G/L account number")
        each get their SAP name appended (`gl_account_number_hkont`), so a name is
        unique within the table and does not depend on which columns are selected.
        """
        names = {
            column: readable_column_name(meaning) or column.lower()
            for column, meaning in COLUMN_DESCRIPTIONS[self.table_name].items()
        }
        counts = Counter(names.values())
        return {column: f"{name}_{column.lower()}" if counts[name] > 1 else name for column, name in names.items()}

    def column_meaning(self, column: str) -> str | None:
        """Meaning of a single column (case-insensitive), or None if undocumented."""
        return COLUMN_DESCRIPTIONS[self.table_name].get(column.strip().upper())

    def describe(self) -> str:
        """The description followed by every documented column, as one text block."""
        lines = [f"{self.table_name}: {self.description}", "", "Columns:"]
        lines += [f"  {name}: {meaning}" for name, meaning in COLUMN_DESCRIPTIONS[self.table_name].items()]
        return "\n".join(lines)
