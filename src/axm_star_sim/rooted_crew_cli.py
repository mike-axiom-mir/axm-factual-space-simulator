from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .rooted_crew import (
    evaluate_action_candidate,
    evolve_derived_principles,
    generate_principled_options,
    load_default_crew,
    load_root_kernel,
    verify_default_crew_binding,
    verify_derived_principles,
    verify_root_kernel,
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="axm-rooted-crew")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("verify-roots")
    sub.add_parser("show-default-crew")

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--candidate-json", required=True)

    options = sub.add_parser("options")
    options.add_argument("--goal", required=True)
    options.add_argument("--options-file", type=Path, required=True)

    evolve = sub.add_parser("evolve")
    evolve.add_argument("--state", type=Path, required=True)
    evolve.add_argument("--additions-file", type=Path, required=True)

    verify_evolution = sub.add_parser("verify-evolution")
    verify_evolution.add_argument("--state", type=Path, required=True)
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "verify-roots":
            kernel = load_root_kernel()
            result = {
                "root_kernel": verify_root_kernel(kernel),
                "default_crew_binding": verify_default_crew_binding(load_default_crew(), kernel),
            }
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        if args.command == "show-default-crew":
            print(json.dumps(load_default_crew(), indent=2, ensure_ascii=False))
            return 0
        if args.command == "evaluate":
            result = evaluate_action_candidate(json.loads(args.candidate_json))
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result["overall_verdict"] == "eligible" else 2
        if args.command == "options":
            rows = json.loads(args.options_file.read_text(encoding="utf-8"))
            result = generate_principled_options(args.goal, rows)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        if args.command == "evolve":
            if args.state.exists():
                state = json.loads(args.state.read_text(encoding="utf-8"))
            else:
                state = {}
            additions = json.loads(args.additions_file.read_text(encoding="utf-8"))
            result = evolve_derived_principles(
                state,
                additions,
                load_root_kernel()["root_commitment_sha256"],
            )
            args.state.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
        if args.command == "verify-evolution":
            state = json.loads(args.state.read_text(encoding="utf-8"))
            result = verify_derived_principles(state)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result["valid"] else 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
