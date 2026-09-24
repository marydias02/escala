"""Use-case-neutral email plumbing: mailbox reading, documents, PDFs.

Everything here is shared by `invoice_extraction` and `payment_matching` and
knows about neither. Nothing in this package imports from a use-case package,
and nothing in it branches on which use case is calling — a use case passes its
own configuration in instead.

The modules were extracted from `invoice_extraction.invoice_utils` and
`invoice_extraction.models` without logic changes; those paths remain as
re-export shims, so existing imports keep working.
"""
