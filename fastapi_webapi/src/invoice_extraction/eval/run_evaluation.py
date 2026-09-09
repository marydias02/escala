"""Run the pipeline over the evaluation dataset and score every field.

    python -m invoice_extraction.eval.run_evaluation

Tracing is turned on first, so each scored row also leaves a full span tree: a
failed field is then one click away from the prompt that produced it.
"""

from mlflow.genai import evaluate
from mlflow.genai.datasets import search_datasets

from invoice_extraction.eval.config import DATASET_NAME, connect
from invoice_extraction.eval.predict import predict_extraction
from invoice_extraction.eval.scorers import ALL_SCORERS
from invoice_extraction.tracing import flush, setup_tracing


def main() -> None:
    connect()
    setup_tracing()

    datasets = search_datasets(filter_string=f"name = '{DATASET_NAME}'")
    if not datasets:
        raise RuntimeError(
            f"No dataset named '{DATASET_NAME}'. "
            "Run: python -m invoice_extraction.eval.create_dataset"
        )

    results = evaluate(
        data=datasets[0],
        predict_fn=predict_extraction,
        scorers=ALL_SCORERS,
    )

    flush()

    print("\n--- metrics ---")
    for name, value in sorted(results.metrics.items()):
        print(f"{name}: {value}")


if __name__ == "__main__":
    main()
