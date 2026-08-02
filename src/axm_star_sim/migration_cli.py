from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from .migration import assess_migration_proposal, create_migration_proposal


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="axm-migration")
    sub = parser.add_subparsers(dest="command", required=True)
    assess = sub.add_parser("assess")
    assess.add_argument("--proposal", type=Path, required=True)
    create = sub.add_parser("create")
    create.add_argument("--start-pin", type=Path, required=True)
    create.add_argument("--migration-type", required=True)
    create.add_argument("--changes-json", required=True)
    create.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "assess":
            result = assess_migration_proposal(json.loads(args.proposal.read_text(encoding="utf-8")))
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result["verdict"] == "ACCEPT" else 2
        proposal = create_migration_proposal(
            json.loads(args.start_pin.read_text(encoding="utf-8")),
            args.migration_type,
            json.loads(args.changes_json),
        )
        args.output.write_text(json.dumps(proposal, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"status":"created","output":str(args.output)}, indent=2))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
