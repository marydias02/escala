"""Build the MLflow evaluation dataset from the hand-labelled ground truth.

    python -m invoice_extraction.eval.create_dataset

Safe to re-run: `merge_records` upserts, so re-labelling a document and running
this again updates that record rather than duplicating it.
"""

import json

from mlflow.genai.datasets import create_dataset, search_datasets

from invoice_extraction.config import DOCS_DIR
from invoice_extraction.eval.config import DATASET_NAME, GROUND_TRUTH_PATH, connect


def load_records() -> list[dict]:
    """Ground truth as MLflow records, failing loudly on a path that does not exist.

    A missing PDF would otherwise surface much later as a mid-evaluation crash.
    """
    labels = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))

    records, missing = [], []
    for item in labels:
        if not (DOCS_DIR / item["pdf"]).is_file():
            missing.append(item["pdf"])
            continue
        records.append(
            {
                # Key must match `predict_extraction(pdf_path=...)`.
                "inputs": {"pdf_path": item["pdf"]},
                "expectations": item["expect"],
                "tags": item.get("tags", {}),
            }
        )

    if missing:
        raise FileNotFoundError(
            "Ground truth references files that do not exist under "
            f"{DOCS_DIR}:\n  " + "\n  ".join(missing)
        )

    return records


def main() -> None:
    experiment_id = connect()
    records = load_records()

    existing = search_datasets(filter_string=f"name = '{DATASET_NAME}'")
    dataset = existing[0] if existing else create_dataset(
        name=DATASET_NAME, experiment_id=experiment_id
    )

    dataset.merge_records(records)
    print(f"{len(records)} record(s) merged into '{dataset.name}'")


if __name__ == "__main__":
    main()
