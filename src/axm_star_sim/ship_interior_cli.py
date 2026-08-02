from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .ship_interior import (
    advance_away_operations,
    answer_command_recall,
    create_interior_state,
    move_to_room,
    perform_room_interaction,
    resolve_command_recall,
    set_continuity_policy,
    validate_interior_archetype,
    verify_interior_state,
)


def load_state(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="axm-ship-interior")
    sub = p.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("--interior-id")

    create = sub.add_parser("create")
    create.add_argument("--seed", required=True)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--continuity-policy-id")

    move = sub.add_parser("move")
    move.add_argument("--state", type=Path, required=True)
    move.add_argument("--room", required=True)

    policy = sub.add_parser("set-policy")
    policy.add_argument("--state", type=Path, required=True)
    policy.add_argument("--policy-id", required=True)

    advance = sub.add_parser("advance")
    advance.add_argument("--state", type=Path, required=True)
    advance.add_argument("--minutes", type=int, required=True)
    advance.add_argument("--authority-level", choices=["routine", "advisory", "command_required"])
    advance.add_argument("--summary")

    recall = sub.add_parser("answer-recall")
    recall.add_argument("--state", type=Path, required=True)

    resolve = sub.add_parser("resolve-recall")
    resolve.add_argument("--state", type=Path, required=True)
    resolve.add_argument("--choice", required=True)
    resolve.add_argument("--reasoning", required=True)

    interact = sub.add_parser("interact")
    interact.add_argument("--state", type=Path, required=True)
    interact.add_argument("--interaction-id", required=True)
    interact.add_argument("--parameters-json", required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("--state", type=Path, required=True)
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "validate":
            result = validate_interior_archetype(args.interior_id)
            print(json.dumps(result, indent=2))
            return 0 if result["valid"] else 1

        if args.command == "create":
            state = create_interior_state(
                args.seed,
                continuity_policy_id=args.continuity_policy_id,
            )
            save_state(args.output, state)
            print(json.dumps({"status": "created", "state": str(args.output)}, indent=2))
            return 0

        state = load_state(args.state)

        if args.command == "move":
            state = move_to_room(state, args.room)
        elif args.command == "set-policy":
            state = set_continuity_policy(state, args.policy_id)
        elif args.command == "advance":
            situation = None
            if args.authority_level:
                situation = {
                    "authority_level": args.authority_level,
                    "summary": args.summary or "Generated ship situation",
                }
            state = advance_away_operations(state, args.minutes, situation)
        elif args.command == "answer-recall":
            state = answer_command_recall(state)
        elif args.command == "resolve-recall":
            state = resolve_command_recall(state, args.choice, args.reasoning)
        elif args.command == "interact":
            parameters = json.loads(args.parameters_json)
            state = perform_room_interaction(state, args.interaction_id, parameters)
        elif args.command == "verify":
            result = verify_interior_state(state)
            print(json.dumps(result, indent=2))
            return 0 if result["valid"] else 1
        else:
            return 1

        save_state(args.state, state)
        print(json.dumps({
            "status": "updated",
            "room": state["current_room_id"],
            "personal_clock_minutes": state["personal_clock_minutes"],
            "expedition_clock_minutes": state["expedition_clock_minutes"],
            "pending_command_recall": state["pending_command_recall"] is not None,
            "state": str(args.state),
        }, indent=2))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
