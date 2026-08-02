from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path

from .adventure_slots import (
    FORGE_MODES,
    act_in_adventure_slot,
    create_adventure_slot,
    export_player_bundle,
    list_adventure_slots,
    prepare_external_forge_request,
    reveal_adventure_slot,
    verify_adventure_slot,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="axm-adventure-slots")
    sub = parser.add_subparsers(dest="command", required=True)

    request = sub.add_parser("prepare-external-request", help="prepare a safe optional AI forge request")
    request.add_argument("--world-seed", required=True)
    request.add_argument("--forge-seed", required=True)
    request.add_argument("--output", type=Path, required=True)

    create = sub.add_parser("create", help="create a persistent offline-playable adventure slot")
    create.add_argument("--slots-dir", type=Path, required=True)
    create.add_argument("--slot-id", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--world-seed", required=True)
    create.add_argument("--forge-seed", required=True)
    create.add_argument("--forge-mode", choices=sorted(FORGE_MODES), default="offline_base")
    create.add_argument("--proposal-file", type=Path)
    create.add_argument("--overwrite", action="store_true")

    list_cmd = sub.add_parser("list", help="list local adventure slots")
    list_cmd.add_argument("--slots-dir", type=Path, required=True)

    act = sub.add_parser("act", help="resolve one blind action inside a saved slot")
    act.add_argument("--slots-dir", type=Path, required=True)
    act.add_argument("--slot-id", required=True)
    act.add_argument("--action", required=True)
    act.add_argument("--entropy-token")

    verify = sub.add_parser("verify", help="verify save files, commitment, and replay")
    verify.add_argument("--slots-dir", type=Path, required=True)
    verify.add_argument("--slot-id", required=True)

    reveal = sub.add_parser("reveal", help="reveal and verify the sealed starting scenario")
    reveal.add_argument("--slots-dir", type=Path, required=True)
    reveal.add_argument("--slot-id", required=True)

    export = sub.add_parser("export-player", help="export only the safe blind player files")
    export.add_argument("--slots-dir", type=Path, required=True)
    export.add_argument("--slot-id", required=True)
    export.add_argument("--output", type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "prepare-external-request":
            request = prepare_external_forge_request(args.world_seed, args.forge_seed, args.output)
            print(json.dumps({"status": "request_prepared", "request_id": request["request_id"], "path": str(args.output)}, indent=2))
            return 0
        if args.command == "create":
            proposal = None
            if args.proposal_file:
                proposal = json.loads(args.proposal_file.read_text(encoding="utf-8"))
            result = create_adventure_slot(
                args.slots_dir,
                args.slot_id,
                args.name,
                args.world_seed,
                args.forge_seed,
                args.forge_mode,
                proposal=proposal,
                overwrite=args.overwrite,
            )
            print(json.dumps({
                "status": "slot_created",
                "slot_id": result["metadata"]["slot_id"],
                "forge_mode": result["metadata"]["forge_mode"],
                "slot_console": str(result["slot_console"]),
                "player_console": str(result["player_console"]),
                "external_connection_required_after_creation": False,
            }, indent=2))
            return 0
        if args.command == "list":
            print(json.dumps({"slots": list_adventure_slots(args.slots_dir)}, indent=2, ensure_ascii=False))
            return 0
        if args.command == "act":
            result = act_in_adventure_slot(
                args.slots_dir,
                args.slot_id,
                args.action,
                entropy_token=args.entropy_token or secrets.token_hex(32),
            )
            print(json.dumps({
                "status": "slot_action_resolved",
                "turn": result["state"]["turn"],
                "action": result["event"]["action_name"],
                "outcome": result["event"]["observation"]["outcome_class"],
                "evidence_stage": result["state"]["evidence_stage"],
                "private_origin_disclosed": False,
            }, indent=2))
            return 0
        if args.command == "verify":
            result = verify_adventure_slot(args.slots_dir, args.slot_id)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result["valid"] else 1
        if args.command == "reveal":
            result = reveal_adventure_slot(args.slots_dir, args.slot_id)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result.get("valid") else 1
        if args.command == "export-player":
            path = export_player_bundle(args.slots_dir, args.slot_id, args.output)
            print(json.dumps({"status": "player_bundle_exported", "path": str(path), "private_files_included": False}, indent=2))
            return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
