"""Defaults for the shared email/PDF primitives.

These are the tunables the moved modules used to read from
`invoice_extraction.config`. They live here so `email_core` depends on no use
case; `invoice_extraction.config` now re-exports them, so its own constants keep
their names and every existing import path still resolves.

A caller that wants a different value passes it as a keyword argument — these
are defaults, not policy.
"""

# -- Zip expansion limits --------------------------------------------------
# Attachments are untrusted input. These bound what a malicious archive can cost
# us, and are enforced against bytes actually decompressed rather than against the
# archive's own declared sizes.

MAX_ZIP_FILES = 30
MAX_ZIP_MEMBER_BYTES = 15 * 1024 * 1024
MAX_ZIP_TOTAL_BYTES = 100 * 1024 * 1024
ZIP_CHUNK_SIZE = 64 * 1024

# -- Scanned documents (vision path) ---------------------------------------
# A scanned page is one large image XObject covering the sheet. It can contain text,
# often incorrect. If the scanned coverage is above a treshold, should be read as image

SCANNED_COVERAGE_THRESHOLD = 1.0

# A scanned bundle can open with a clean cover sheet, so look past page 1.
COVERAGE_SCAN_PAGES = 5

# 72 DPI already reads correctly on the known scans; 110 is margin for finer print.
RENDER_DPI = 110

# Caps the number of pages sent as images (usually info is at start)
RENDER_MAX_PAGES = 5

# -- Attachment conversion to PDF ------------------------------------------

# Caps the rows rendered per spreadsheet sheet.
MAX_SHEET_ROWS = 1000
