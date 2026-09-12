import argparse
import json
import os
import sys
from pathlib import Path

from revision.config import AppConfig, load_config
from revision.domain import Verdict
from revision.service import open_station


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RE-VISION active inspection starter")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="run deterministic fixtures without hardware or weights")
    demo.add_argument(
        "--scenario", choices=["clean", "scratch", "uncertain", "glare"], default="scratch"
    )
    demo.add_argument("--output", type=Path, default=Path("outputs/demo"))
    demo.add_argument("--part-id", default="demo-part")
    inspect = sub.add_parser("inspect", help="run one configured inspection")
    inspect.add_argument("--config", type=Path, required=True)
    inspect.add_argument("--part-id", required=True)
    serve = sub.add_parser("serve", help="start the optional local station API")
    serve.add_argument("--config", type=Path, required=True)
    serve.add_argument("--port", type=int, default=8000)
    dataset = sub.add_parser("dataset", help="validate and split a JSONL image dataset")
    dataset.add_argument("manifest", type=Path)
    dataset.add_argument("--output", type=Path)
    dataset.add_argument("--seed", type=int, default=42)
    metrics = sub.add_parser("evaluate", help="evaluate one labeled inspection per part")
    metrics.add_argument("results", type=Path)
    flush = sub.add_parser("flush", help="retry the cloud outbox using an HTTPS gateway")
    flush.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "dataset":
            from revision.data.manifest import load_dataset, split_dataset, write_splits

            rows = load_dataset(args.manifest)
            summary = {"validated_images": len(rows)}
            if args.output:
                splits = split_dataset(rows, args.seed)
                write_splits(splits, args.output)
                summary["split_images"] = {key: len(value) for key, value in splits.items()}
            print(json.dumps(summary))
            return 0
        if args.command == "evaluate":
            from revision.data.metrics import evaluate

            rows = [
                json.loads(line) for line in args.results.read_text().splitlines() if line.strip()
            ]
            print(json.dumps(evaluate(rows), indent=2))
            return 0
        config = (
            AppConfig(scenario=args.scenario, output_dir=args.output.resolve())
            if args.command == "demo"
            else load_config(args.config)
        )
        if args.command == "serve":
            import uvicorn

            from revision.api import create_app

            uvicorn.run(create_app(config), host="127.0.0.1", port=args.port, workers=1)
            return 0
        if args.command == "flush":
            from revision.adapters.http_publisher import HttpPublisher
            from revision.adapters.sqlite_store import SQLiteStore

            publisher = HttpPublisher(
                os.environ.get("REVISION_TELEMETRY_URL", ""),
                os.environ.get("REVISION_TELEMETRY_TOKEN", ""),
            )
            summary = SQLiteStore(config.output_dir / "revision.db").flush(publisher)
            print(json.dumps(summary))
            return 1 if summary["failed"] else 0
        with open_station(config) as station:
            result = station.inspect(args.part_id)
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False, allow_nan=False))
            # FAIL/REVIEW are valid workflow results; ERROR is a process failure.
            return 1 if result.verdict == Verdict.ERROR else 0
    except (ValueError, OSError, RuntimeError, ImportError, KeyError, TypeError) as error:
        print(f"RE-VISION: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
