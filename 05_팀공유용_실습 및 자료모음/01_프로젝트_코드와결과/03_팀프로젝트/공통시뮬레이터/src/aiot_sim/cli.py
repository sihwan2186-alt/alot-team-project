import argparse
import json
import logging
from pathlib import Path

from .catalog import generate as generate_master
from .config import load
from .pipeline.aggregator import aggregate
from .pipeline.labeler import label_run
from .pipeline.reporter import report
from .pipeline.simulator import simulate
from .pipeline.validator import validate
from .profiles import generate as generate_profiles


def main():
    parser = argparse.ArgumentParser(
        description="Smart Campus synthetic environmental simulator"
    )
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "generate-master", "generate-profiles"):
        sub.add_parser(name)
    sim = sub.add_parser("simulate")
    for name, kind in (
        ("days", int),
        ("seed", int),
        ("step-minutes", int),
        ("start-date", str),
    ):
        sim.add_argument("--" + name, type=kind)
    sim.add_argument("--room-id", action="append")
    sim.add_argument("--run-id", required=True)
    for name in ("aggregate", "validate", "report", "label"):
        p = sub.add_parser(name)
        p.add_argument("--run-id", required=True)
        if name == "aggregate":
            p.add_argument("--minutes", type=int)
    args = parser.parse_args()
    root = args.root.resolve()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        override = {
            k: getattr(args, k, None)
            for k in ("days", "seed", "step_minutes", "start_date")
        }
        override["room_ids"] = getattr(args, "room_id", None)
        cfg = load(root, override)
        if args.command in {"init", "generate-master"}:
            generate_master(root)
        if args.command in {"init", "generate-profiles"}:
            generate_master(root)
            generate_profiles(root, cfg["rules"]["room_profile"])
        if args.command == "simulate":
            generate_master(root)
            generate_profiles(root, cfg["rules"]["room_profile"])
            print(simulate(root, cfg, args.run_id))
        elif args.command in {"aggregate", "validate", "report", "label"}:
            if Path(args.run_id).name != args.run_id or args.run_id in {".", ".."}:
                raise ValueError("Invalid run ID")
            run = root / cfg["output_path"] / args.run_id
            if args.command == "label":
                print(json.dumps(label_run(run), ensure_ascii=False, indent=2))
            elif args.command == "aggregate":
                print(
                    json.dumps(
                        {
                            "rows": aggregate(
                                run,
                                args.minutes
                                if args.minutes is not None
                                else cfg["aggregate_minutes"],
                            )
                        }
                    )
                )
            elif args.command == "validate":
                result = validate(run)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                if not result["valid"]:
                    return 1
            else:
                result = report(run)
                print(
                    json.dumps(
                        {k: v for k, v in result.items() if k != "csv_files"},
                        ensure_ascii=False,
                        indent=2,
                    )
                )
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0
