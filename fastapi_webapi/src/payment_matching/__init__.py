"""Payment matching: a pool of payment information, and allocation over it.

`email_pipeline` reads the payments mailbox and records what each message says
about a payment — body information plus any payment notes. Allocation against
bank extracts consumes that pool.

Independent of `invoice_extraction`: own entry point, advisory lock, tables and
mailbox. The two share only `email_core`.
"""
