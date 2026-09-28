"""Download MLflow traces from blob storage and import them into a local MLflow server.

The blob artifact store only holds span data (`<exp_id>/traces/<trace_id>/artifacts/traces.json`);
the spans are replayed into a local experiment so the MLflow UI can show them.

Start a local server first (from fastapi_webapi/):

    uv run mlflow server --host 127.0.0.1 --port 5000

Then:

    python scripts/view_traces.py                                     # the TRACE_IDS below
    python scripts/view_traces.py tr-f38a...                          # trace in experiment 1
    python scripts/view_traces.py tr-aaa tr-bbb --exp 2               # several traces
    python scripts/view_traces.py downloads/1/traces/tr-.../artifacts/traces.json   # local file
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import mlflow
from download_blob_files import DEFAULT_OUT_DIR, download
from loguru import logger
from mlflow.tracing.utils.copy import copy_trace_to_experiment

# Default trace ids, used when none are passed on the command line.
TRACE_IDS = ["tr-f38a34e1035454f5e428be10c423a813"]

DEFAULT_TRACKING_URI = "http://127.0.0.1:5000"
DEFAULT_EXPERIMENT = "imported_traces"


def trace_key(exp_id: str, trace_id: str) -> str:
    """Blob key of a trace's span data."""
    return f"{exp_id}/traces/{trace_id}/artifacts/traces.json"


def resolve(source: str, exp_id: str, out_dir: Path) -> tuple[str, Path | None]:
    """(original trace id, local traces.json path) for a local file or a blob trace id."""
    path = Path(source)
    if path.is_file():
        return path.parent.parent.name, path
    return source, download(trace_key(exp_id, source), out_dir)


def import_trace(path: Path, original_id: str, experiment_id: str) -> str:
    """Replay the spans in `path` into the experiment; returns the new trace id."""
    spans = json.loads(path.read_text(encoding="utf-8"))["spans"]
    # Root span must come first: children are attached to its new trace id
    spans.sort(key=lambda s: s["parent_span_id"] is not None)
    new_id = copy_trace_to_experiment({"data": {"spans": spans}}, experiment_id=experiment_id)
    mlflow.set_trace_tag(new_id, "original_trace_id", original_id)
    return new_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sources", nargs="*", help="trace ids (tr-...) or local traces.json paths (default: TRACE_IDS)")
    parser.add_argument("--exp", default="1", help="remote experiment id in the blob path (default: 1)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, help="download directory")
    parser.add_argument("--tracking-uri", default=DEFAULT_TRACKING_URI, help="local MLflow server")
    parser.add_argument("--experiment", default=DEFAULT_EXPERIMENT, help="local experiment name")
    args = parser.parse_args()
    sources = args.sources or TRACE_IDS

    mlflow.set_tracking_uri(args.tracking_uri)
    experiment_id = mlflow.set_experiment(args.experiment).experiment_id

    failures = 0
    for source in sources:
        original_id, path = resolve(source, args.exp, args.out)
        if path is None:
            failures += 1
            continue
        new_id = import_trace(path, original_id, experiment_id)
        logger.info(
            f"{original_id} -> {args.tracking_uri}/#/experiments/{experiment_id}/traces?selectedEvaluationId={new_id}"
        )

    logger.info(f"Imported {len(sources) - failures}/{len(sources)} trace(s) into '{args.experiment}'")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
