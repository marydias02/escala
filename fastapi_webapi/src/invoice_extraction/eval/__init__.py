"""MLflow evaluation of the extraction pipeline against hand-labelled documents.

Ground truth lives in `docs/eval_ground_truth.json` — one record per document,
`pdf` relative to DOCS_DIR so the set is not bound to one machine.

    python -m invoice_extraction.eval.create_dataset
    python -m invoice_extraction.eval.run_evaluation
"""
