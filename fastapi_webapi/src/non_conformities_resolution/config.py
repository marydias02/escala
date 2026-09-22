"""Tunable constants for the non-conformities resolution pipeline."""

# How many processes `resolution_pipeline.run` handles per invocation.
# None = no limit. A testing knob, independent of any future scheduler cadence.
BATCH_LIMIT: int | None = None

# Persist status/SAP changes to Postgres. Off lets the pipeline be exercised (and
# its branch decisions inspected via print_summary) with no database running.
WRITE_TO_DB = True

# Whether `sap.sap_client` calls a real SAP integration. There is none yet, so
# this stays False and every sap_client function returns a logged stub result.
# Flip this, not the call sites, once a real integration exists.
SAP_ENABLED = False

# Below this confidence a parsed buyer reply is treated as unclear and goes for manual review.
BUYER_REPLY_MIN_CONFIDENCE = 0.7

# -- Tracing (MLflow) ---------------------------------------------------------
# Same master switch as invoice_extraction.config; unused until this pipeline
# adopts invoice_extraction.tracing.

ENABLE_TRACING = False

MLFLOW_EXPERIMENT = "non_conformities_resolution"
