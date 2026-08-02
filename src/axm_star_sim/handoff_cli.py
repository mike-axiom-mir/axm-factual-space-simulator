from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from .handoff import audit_package


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="axm-handoff")
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--full", action="store_true")
    audit.add_argument("--root", type=Path)
    audit.add_argument("--output", type=Path)
    show = sub.add_parser("show")
    args = parser.parse_args(argv)
    try:
        if args.command == "show":
            root = Path(__file__).resolve().parents[2]
            print((root/"LOCAL_INTAKE_HANDOFF.txt").read_text(encoding="utf-8"))
            return 0
        result = audit_package(args.root, full=args.full, check_manifest=True)
        if args.output:
            args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["valid"] else 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
