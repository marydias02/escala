"""Run the pipeline over the evaluation dataset and score every field.

    python -m invoice_extraction.eval.run_evaluation
    python -m invoice_extraction.eval.run_evaluation --pdf ACME_2024

Tracing is turned on first, so each scored row also leaves a full span tree: a
failed field is then one click away from the prompt that produced it.
"""

import argparse

from mlflow.genai import evaluate
from mlflow.genai.datasets import search_datasets

from invoice_extraction.eval.config import DATASET_NAME, connect
from invoice_extraction.eval.predict import predict_extraction
from invoice_extraction.eval.scorers import ALL_SCORERS
from invoice_extraction.tracing import flush, setup_tracing


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pdf",
        help="Only score records whose pdf_path contains this substring.",
    )
    return parser.parse_args()


def select_records(dataset, pdf: str) -> list[dict]:
    """Dataset rows whose pdf_path matches, as records `evaluate` accepts.

    Passing a list drops the dataset link on the run, so the filtered run is not
    grouped with full-dataset runs in MLflow.
    """
    records = [
        row
        for row in dataset.to_df().to_dict("records")
        if pdf in row["inputs"]["pdf_path"]
    ]
    if not records:
        raise RuntimeError(f"No record in '{dataset.name}' matching --pdf {pdf!r}.")
    return records


def main() -> None:
    args = parse_args()
    connect()
    setup_tracing()

    datasets = search_datasets(filter_string=f"name = '{DATASET_NAME}'")
    if not datasets:
        raise RuntimeError(
            f"No dataset named '{DATASET_NAME}'. "
            "Run: python -m invoice_extraction.eval.create_dataset"
        )

    data = datasets[0]
    if args.pdf is not None:
        records = select_records(data, args.pdf)
        print(f"Scoring {len(records)} record(s) matching {args.pdf!r}")
        data = records

    results = evaluate(
        data=data,
        predict_fn=predict_extraction,
        scorers=ALL_SCORERS,
    )

    flush()

    print("\n--- metrics ---")
    for name, value in sorted(results.metrics.items()):
        print(f"{name}: {value}")


if __name__ == "__main__":
    main()
