"""Shared settings for the evaluation scripts."""

import mlflow

from config.settings import settings
from invoice_extraction.config import DOCS_DIR, MLFLOW_EXPERIMENT

GROUND_TRUTH_PATH = DOCS_DIR / "eval_ground_truth.json"

DATASET_NAME = "invoice-extraction-v1"

# Amounts are compared with a tolerance: a float round-trip must not fail a match.
AMOUNT_TOLERANCE = 0.01


def connect() -> str:
    """Point MLflow at the tracking server and return the experiment id.

    Datasets need a real tracking server (a backend store), so an unset URI is a
    hard error here — unlike in `tracing`, where it just disables tracing.
    """
    tracking_uri = settings.MLFLOW_TRACKING_URI
    if not tracking_uri:
        raise RuntimeError(
            "MLFLOW_TRACKING_URI is not set — evaluation needs a tracking server. "
            "Start one with:\n"
            "  mlflow server --backend-store-uri sqlite:///mlflow.db "
            "--default-artifact-root ./mlruns --port 5000"
        )

    mlflow.set_tracking_uri(tracking_uri)
    return mlflow.set_experiment(MLFLOW_EXPERIMENT).experiment_id
