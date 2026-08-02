from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .ship_blueprint import (
    advance_ship_state,
    apply_encounter_effects,
    apply_failure_mode,
    create_ship_state,
    evaluate_ship,
    fault_propagation_paths,
    qualification_gap_plan,
    role_perspective_snapshot,
    task_readiness,
    validate_blueprint,
    verify_ship_state,
)


def load_state(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="axm-ship-blueprint")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("validate")

    create = sub.add_parser("create-state")
    create.add_argument("--seed", required=True)
    create.add_argument("--output", type=Path, required=True)

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--state", type=Path, required=True)

    advance = sub.add_parser("advance")
    advance.add_argument("--state", type=Path, required=True)
    advance.add_argument("--minutes", type=float, required=True)
    advance.add_argument("--solar-flux-ratio", type=float)
    advance.add_argument("--data-generated-gb", type=float, default=0.0)

    fault = sub.add_parser("fault")
    fault.add_argument("--state", type=Path, required=True)
    fault.add_argument("--failure-mode-id", required=True)

    encounter = sub.add_parser("encounter")
    encounter.add_argument("--state", type=Path, required=True)
    encounter.add_argument("--encounter-file", type=Path, required=True)

    role = sub.add_parser("role-perspective")
    role.add_argument("--state", type=Path, required=True)
    role.add_argument("--role-id", required=True)

    readiness = sub.add_parser("task-readiness")
    readiness.add_argument("--state", type=Path, required=True)
    readiness.add_argument("--role-id", required=True)
    readiness.add_argument("--requirements-json", required=True)

    gaps = sub.add_parser("qualification-plan")
    gaps.add_argument("--state", type=Path, required=True)
    gaps.add_argument("--role-id", required=True)
    gaps.add_argument("--requirements-json", required=True)

    paths = sub.add_parser("fault-paths")
    paths.add_argument("--system-id", required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("--state", type=Path, required=True)
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "validate":
            result = validate_blueprint()
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result["valid"] else 1
        if args.command == "create-state":
            state = create_ship_state(args.seed)
            save_state(args.output, state)
            print(json.dumps({"status": "created", "state": str(args.output)}, indent=2))
            return 0
        if args.command == "fault-paths":
            print(json.dumps(fault_propagation_paths(args.system_id), indent=2))
            return 0

        state = load_state(args.state)
        if args.command == "evaluate":
            print(json.dumps(evaluate_ship(state), indent=2, ensure_ascii=False))
            return 0
        if args.command == "advance":
            state = advance_ship_state(
                state,
                args.minutes,
                solar_flux_ratio=args.solar_flux_ratio,
                data_generated_gb=args.data_generated_gb,
            )
            save_state(args.state, state)
        elif args.command == "fault":
            state = apply_failure_mode(state, args.failure_mode_id)
            save_state(args.state, state)
        elif args.command == "encounter":
            encounter = json.loads(args.encounter_file.read_text(encoding="utf-8"))
            state = apply_encounter_effects(state, encounter)
            save_state(args.state, state)
        elif args.command == "role-perspective":
            print(json.dumps(role_perspective_snapshot(state, args.role_id), indent=2, ensure_ascii=False))
            return 0
        elif args.command == "task-readiness":
            requirements = json.loads(args.requirements_json)
            print(json.dumps(task_readiness(state, args.role_id, requirements), indent=2))
            return 0
        elif args.command == "qualification-plan":
            requirements = json.loads(args.requirements_json)
            print(json.dumps(qualification_gap_plan(state, args.role_id, requirements), indent=2))
            return 0
        elif args.command == "verify":
            result = verify_ship_state(state)
            print(json.dumps(result, indent=2))
            return 0 if result["valid"] else 1
        else:
            return 1

        print(json.dumps({
            "status": "updated",
            "state": str(args.state),
            "evaluation": evaluate_ship(state),
        }, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
