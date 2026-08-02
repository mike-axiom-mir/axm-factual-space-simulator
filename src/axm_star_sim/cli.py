from __future__ import annotations

import argparse
import copy
import json
import sys
import secrets
from pathlib import Path

from .atlas import (
    create_revisit_packet,
    import_normalized_catalog,
    record_visit,
    register_system_location,
    revisit_options,
    verify_visit_chain,
    write_atlas_files,
)
from .beacons import fetch_drand_latest, verify_drand_packet
from .blind_forge import (
    forge_blind_scenario,
    resolve_session_action,
    reveal_session,
    verify_session,
    write_blind_forge_session,
)
from .catalog import normalize_nasa_snapshot, summarize_catalog
from .command import (
    COMMAND_MODES,
    append_discussion_message,
    plan_command,
    proposal,
    resolve_collaboration,
)
from .entropy import ENTROPY_MODES, create_commitment, create_master_seed_receipt
from .generator import generate_system
from .io import (
    append_runtime_event,
    load_ledger,
    load_pending_session,
    save_pending_session,
    refresh_output_manifest,
    update_command_mode,
    write_system,
)
from .runtime import canonical_hash, initial_runtime_state, resolve_turn, verify_ledger
from .sources import update_jpl_sbdb, update_nasa_exoplanet_archive
from .technology_core import build_ship_technology_profile, eligible_core_ids, load_technology_core_registry


def parse_weights(raw: str | None) -> dict[str, int] | None:
    if not raw:
        return None
    result: dict[str, int] = {}
    for item in raw.split(","):
        key, sep, value = item.partition("=")
        if not sep:
            raise argparse.ArgumentTypeError(f"invalid weight entry: {item}")
        result[key.strip().lower()] = int(value)
    return result


def _read_json(path: Path | None) -> dict | None:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _read_reveals(paths: list[Path] | None) -> list[dict[str, str]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in (paths or [])]


def _load_verified(output: Path) -> tuple[dict, dict, list[dict]]:
    system = json.loads((output / "system.json").read_text(encoding="utf-8"))
    state = json.loads((output / "runtime_state.json").read_text(encoding="utf-8"))
    events = load_ledger(output / "event_ledger.jsonl")
    valid, checks, rebuilt = verify_ledger(system, events)
    if not valid:
        raise ValueError(f"existing event ledger failed verification: {checks[-1]}")
    pending = load_pending_session(output)
    compare_state = copy.deepcopy(state)
    compare_state.setdefault("command", {})["pending_session_id"] = None
    rebuilt.setdefault("command", {})["pending_session_id"] = None
    if canonical_hash(compare_state) != canonical_hash(rebuilt):
        raise ValueError("runtime_state.json does not match the verified event ledger")
    return system, state, events


def _add_entropy_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--entropy-mode", choices=sorted(ENTROPY_MODES), default="mixed_live")
    parser.add_argument("--beacon-file", type=Path)
    parser.add_argument("--reveal", type=Path, action="append")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="axm-star-sim")
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate", help="generate a stable initial system and unresolved adventure")
    generate.add_argument("--seed", required=True)
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--weights", help="comma-separated values such as wonder=35,mystery=30")
    generate.add_argument(
        "--command-mode",
        choices=sorted(COMMAND_MODES),
        default="autonomous_deterministic",
        help="select one of the four command-authority modes",
    )

    set_mode = sub.add_parser("set-command-mode", help="change mode before the first resolved event")
    set_mode.add_argument("--output", type=Path, required=True)
    set_mode.add_argument("--mode", choices=sorted(COMMAND_MODES), required=True)

    run_command = sub.add_parser("run-command", help="plan command authority and resolve one event when authorized")
    run_command.add_argument("--output", type=Path, required=True)
    run_command.add_argument("--mode", choices=sorted(COMMAND_MODES))
    run_command.add_argument("--human-action")
    run_command.add_argument("--human-rationale", default="")
    run_command.add_argument("--ai-action")
    run_command.add_argument("--ai-rationale", default="")
    run_command.add_argument("--turns", type=int, default=1, help="autonomous mode can advance multiple deterministic turns")
    _add_entropy_args(run_command)

    council_message = sub.add_parser("council-message", help="append a human or AI message to a pending disagreement")
    council_message.add_argument("--output", type=Path, required=True)
    council_message.add_argument("--speaker", choices=["human", "ai"], required=True)
    council_message.add_argument("--message", required=True)
    council_message.add_argument("--proposed-action")

    council_resolve = sub.add_parser("council-resolve", help="resolve a pending council only when final votes match")
    council_resolve.add_argument("--output", type=Path, required=True)
    council_resolve.add_argument("--human-action", required=True)
    council_resolve.add_argument("--ai-action", required=True)
    council_resolve.add_argument("--summary", default="")
    _add_entropy_args(council_resolve)

    seed = sub.add_parser("create-seed", help="resolve a new master seed from live, beacon, or party entropy")
    seed.add_argument("--mode", choices=sorted(ENTROPY_MODES), required=True)
    seed.add_argument("--phrase", default="")
    seed.add_argument("--beacon-file", type=Path)
    seed.add_argument("--reveal", type=Path, action="append")
    seed.add_argument("--output", type=Path, required=True)

    commitment = sub.add_parser("create-commitment", help="create public and private files for party commit-reveal")
    commitment.add_argument("--label", required=True)
    commitment.add_argument("--value", required=True)
    commitment.add_argument("--output", type=Path, required=True)

    evolve = sub.add_parser("evolve", help="direct low-level event resolution; run-command is preferred")
    evolve.add_argument("--output", type=Path, required=True, help="generated adventure directory")
    evolve.add_argument("--action", required=True, help="exact action text or 1-based action number")
    evolve.add_argument("--mode", choices=sorted(ENTROPY_MODES), default="mixed_live")
    evolve.add_argument("--beacon-file", type=Path)
    evolve.add_argument("--reveal", type=Path, action="append")

    replay = sub.add_parser("verify-ledger", help="replay and verify the command/event ledger")
    replay.add_argument("--output", type=Path, required=True)

    beacon = sub.add_parser("fetch-beacon", help="fetch, preserve, and attempt verification of the latest drand quicknet packet")
    beacon.add_argument("--source", choices=["drand"], default="drand")
    beacon.add_argument("--output", type=Path, required=True)

    verify_beacon = sub.add_parser("verify-beacon", help="structurally and cryptographically verify a saved drand quicknet packet")
    verify_beacon.add_argument("--input", type=Path, required=True)
    verify_beacon.add_argument("--write-back", action="store_true", help="store the latest verification result inside the packet")

    update = sub.add_parser("update-sources", help="create timestamped astronomy source snapshots")
    update.add_argument("--source", choices=["nasa_exoplanet_archive", "jpl_sbdb"], required=True)
    update.add_argument("--output", type=Path, required=True)
    update.add_argument("--limit", type=int, default=500)
    update.add_argument("--query", help="object name/designation for JPL SBDB")

    normalize = sub.add_parser("normalize-snapshot", help="normalize a pinned external snapshot into AXM catalog JSONL")
    normalize.add_argument("--source", choices=["nasa_exoplanet_archive"], required=True)
    normalize.add_argument("--snapshot", type=Path, required=True)
    normalize.add_argument("--output", type=Path, required=True)

    summarize = sub.add_parser("summarize-catalog", help="create a bias-warned empirical summary from normalized JSONL")
    summarize.add_argument("--input", type=Path, required=True)
    summarize.add_argument("--output", type=Path, required=True)

    technology = sub.add_parser("technology-cores", help="inspect the source-pinned 2027 ship technology catalog")
    technology.add_argument("--seed", help="select one reference lineage using the same equal-slot seed policy as generation")
    technology.add_argument("--output", type=Path, help="optional JSON output path")

    atlas_status = sub.add_parser("atlas-status", help="inspect mapped, visited, and revisitable locations")
    atlas_status.add_argument("--output", type=Path, required=True, help="generated adventure directory")

    atlas_import = sub.add_parser("atlas-import-system", help="attach another generated system to an existing expedition atlas")
    atlas_import.add_argument("--output", type=Path, required=True, help="existing generated adventure directory")
    atlas_import.add_argument("--system-json", type=Path, required=True)
    atlas_import.add_argument("--visit-note", default="Imported expedition branch registered in the persistent atlas.")

    revisit = sub.add_parser("revisit-location", help="create a revision-safe render packet for an old visited location")
    revisit.add_argument("--output", type=Path, required=True, help="generated adventure directory")
    revisit.add_argument("--location-id", required=True)
    revisit.add_argument("--visual-engine-version", required=True)
    revisit.add_argument("--asset-engine-version", default="unversioned")
    revisit.add_argument("--camera-language", default="crew-memory-reconstruction")

    atlas_catalog = sub.add_parser("atlas-import-catalog", help="add a normalized source snapshot without rewriting old map history")
    atlas_catalog.add_argument("--output", type=Path, required=True, help="generated adventure directory")
    atlas_catalog.add_argument("--snapshot", type=Path, required=True, help="axm.normalized-atlas-catalog.v1 JSON file")

    blind_forge = sub.add_parser("forge-blind-seed", help="create a sealed AI-reasoned scenario before a separate AI or human explores it")
    blind_forge.add_argument("--world-seed", required=True)
    blind_forge.add_argument("--forge-seed", required=True, help="private seed used only by the scenario-forging side")
    blind_forge.add_argument("--output", type=Path, required=True)

    blind_act = sub.add_parser("blind-act", help="host-resolve one player action without exposing the private scenario")
    blind_act.add_argument("--output", type=Path, required=True)
    blind_act.add_argument("--action", required=True)
    blind_act.add_argument("--entropy-token", help="host entropy; omitted means fresh local entropy")

    blind_verify = sub.add_parser("verify-blind-session", help="verify the sealed scenario and every resolved blind event")
    blind_verify.add_argument("--output", type=Path, required=True)

    blind_reveal = sub.add_parser("reveal-blind-session", help="create a post-play reveal and verification packet")
    blind_reveal.add_argument("--output", type=Path, required=True)
    return parser


def _execute_decision(args: argparse.Namespace, system: dict, state: dict, decision: dict) -> dict:
    entropy_mode = "deterministic" if decision.get("mode") == "autonomous_deterministic" else args.entropy_mode
    state_for_event = copy.deepcopy(state)
    state_for_event.setdefault("command", {})["pending_session_id"] = None
    event, updated = resolve_turn(
        system=system,
        state=state_for_event,
        action=decision["selected_action"],
        entropy_mode=entropy_mode,
        beacon=_read_json(args.beacon_file),
        party_reveals=_read_reveals(args.reveal),
        command_decision=decision,
    )
    manifest = append_runtime_event(args.output, event, updated)
    return {
        "status": "event_resolved",
        "turn": event["turn"],
        "command_mode": decision["mode"],
        "authority": decision["authority"],
        "action": event["action"],
        "outcome": event["outcome"]["title"],
        "crew_recommendation_followed": decision.get("crew_recommendation_followed"),
        "warnings": decision.get("warnings", []),
        "entropy_mode": event["entropy"]["mode"],
        "predetermined_by_master_seed": event["predetermined_by_master_seed"],
        "command_hash": decision["command_hash"],
        "event_hash": event["event_hash"],
        "physics": {
            "target": event["physics_expectation"]["target_planet_name"],
            "expected_snr": event["physics_expectation"]["sensor"]["expected_snr"],
            "thermal_load_ratio": event["physics_expectation"]["thermal"]["thermal_load_ratio"],
            "radiation_risk_index": event["physics_expectation"]["radiation"]["shielded_risk_index"],
            "one_way_light_time_s": event["physics_expectation"]["communications"]["one_way_light_time_s"],
            "trajectory_days": event["physics_expectation"]["trajectory"]["transfer_time_days"],
        },
        "new_action_count": len(event["new_action_menu"]["actions"]),
        "active_threads": event["new_action_menu"]["active_thread_ids"],
        "files": manifest["files"],
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "forge-blind-seed":
            system = generate_system(args.world_seed).to_dict()
            private_payload, public_bundle = forge_blind_scenario(system, args.forge_seed)
            paths = write_blind_forge_session(args.output, system, private_payload, public_bundle)
            print(json.dumps({
                "status": "blind_seed_forged",
                "system": system["name"],
                "system_id": system["system_id"],
                "commitment": paths["commitment"],
                "player_public": str(args.output / "player_public"),
                "forge_private": str(args.output / "forge_private"),
                "rule": "Give only player_public to the exploring AI or human.",
            }, indent=2))
            return 0

        if args.command == "blind-act":
            token = args.entropy_token or secrets.token_hex(32)
            result = resolve_session_action(args.output, args.action, token)
            event = result["event"]
            print(json.dumps({
                "status": "blind_action_resolved",
                "turn": event["turn"],
                "action": event["action_name"],
                "outcome_class": event["observation"]["outcome_class"],
                "evidence_stage": event["evidence_stage_after"],
                "event_hash": event["event_hash"],
                "player_console": str(args.output / "player_public" / "player_console.html"),
                "private_origin_disclosed": False,
            }, indent=2))
            return 0

        if args.command == "verify-blind-session":
            private_payload = json.loads((args.output / "forge_private" / "hidden_scenario.json").read_text(encoding="utf-8"))
            public_bundle = json.loads((args.output / "player_public" / "mission_bundle.json").read_text(encoding="utf-8"))
            events = [json.loads(line) for line in (args.output / "player_public" / "event_ledger.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            tokens = json.loads((args.output / "forge_private" / "ENTROPY_TOKENS.json").read_text(encoding="utf-8"))
            result = verify_session(private_payload, public_bundle, events, tokens)
            print(json.dumps(result, indent=2))
            return 0 if result.get("valid") else 1

        if args.command == "reveal-blind-session":
            result = reveal_session(args.output)
            print(json.dumps({
                "status": "blind_session_revealed" if result.get("valid") else "reveal_verification_failed",
                "valid": result.get("valid"),
                "reveal_directory": str(args.output / "post_play_reveal"),
                "events": len(result.get("checks", [])),
            }, indent=2))
            return 0 if result.get("valid") else 1

        if args.command == "generate":
            weights = parse_weights(args.weights)
            system = generate_system(args.seed, weights)
            manifest = write_system(args.output, system.to_dict(), args.command_mode)
            print(json.dumps({
                "status": "created",
                "system": system.name,
                "system_id": system.system_id,
                "output": str(args.output),
                "command_mode": args.command_mode,
                "unresolved_future": True,
                "files": manifest["files"],
            }, indent=2))
            return 0

        if args.command == "set-command-mode":
            manifest = update_command_mode(args.output, args.mode)
            print(json.dumps({"status": "command_mode_changed", "mode": args.mode, "files": manifest["files"]}, indent=2))
            return 0

        if args.command == "run-command":
            if args.turns < 1:
                raise ValueError("--turns must be at least 1")
            results = []
            for _index in range(args.turns):
                system, state, _ = _load_verified(args.output)
                if load_pending_session(args.output):
                    raise ValueError("a collaborative command discussion is already pending; use council-message or council-resolve")
                mode = args.mode or state.get("command", {}).get("active_mode") or system.get("active_command_mode")
                if args.turns > 1 and mode != "autonomous_deterministic":
                    raise ValueError("multiple automatic turns are only allowed in autonomous_deterministic mode")
                human = proposal("human", args.human_action, args.human_rationale) if args.human_action else None
                ai = proposal("ai", args.ai_action, args.ai_rationale) if args.ai_action else None
                plan = plan_command(system=system, state=state, mode=mode, human_proposal=human, ai_proposal=ai)
                if plan["status"] == "discussion_required":
                    manifest = save_pending_session(args.output, plan["session"], state)
                    print(json.dumps({
                        "status": "discussion_required",
                        "session_id": plan["session"]["session_id"],
                        "human_vote": plan["session"]["proposals"]["human"]["action"],
                        "ai_vote": plan["session"]["proposals"]["ai"]["action"],
                        "rule": plan["session"]["rule"],
                        "command_console": str(args.output / "command_console.html"),
                        "files": manifest["files"],
                    }, indent=2))
                    return 3
                results.append(_execute_decision(args, system, state, plan["decision"]))
            if len(results) == 1:
                print(json.dumps(results[0], indent=2))
            else:
                print(json.dumps({
                    "status": "autonomous_run_complete",
                    "turns_resolved": len(results),
                    "fully_deterministic": True,
                    "events": results,
                }, indent=2))
            return 0

        if args.command == "council-message":
            system, state, _ = _load_verified(args.output)
            session = load_pending_session(args.output)
            if not session:
                raise ValueError("no pending command council session exists")
            updated = append_discussion_message(
                system=system,
                state=state,
                session=session,
                speaker=args.speaker,
                message=args.message,
                proposed_action=args.proposed_action,
            )
            manifest = save_pending_session(args.output, updated, state)
            print(json.dumps({
                "status": "discussion_message_added",
                "session_id": updated["session_id"],
                "message_count": len(updated["discussion"]),
                "current_human_vote": updated["proposals"]["human"]["action"],
                "current_ai_vote": updated["proposals"]["ai"]["action"],
                "files": manifest["files"],
            }, indent=2))
            return 0

        if args.command == "council-resolve":
            system, state, _ = _load_verified(args.output)
            session = load_pending_session(args.output)
            if not session:
                raise ValueError("no pending command council session exists")
            decision = resolve_collaboration(
                system=system,
                state={**state, "command": {**state.get("command", {}), "pending_session_id": None}},
                session=session,
                human_final_action=args.human_action,
                ai_final_action=args.ai_action,
                summary=args.summary,
            )
            print(json.dumps(_execute_decision(args, system, state, decision), indent=2))
            return 0

        if args.command == "technology-cores":
            registry = load_technology_core_registry()
            payload = {
                "status": "technology_catalog",
                "as_of_date": registry["as_of_date"],
                "planning_horizon_year": registry["planning_horizon_year"],
                "eligible_core_ids": eligible_core_ids(registry),
                "policy": registry["policy"],
            }
            if args.seed:
                payload["selected_profile"] = build_ship_technology_profile(args.seed)
            else:
                payload["cores"] = {
                    core_id: registry["cores"][core_id]
                    for core_id in eligible_core_ids(registry)
                }
                payload["supporting_technologies"] = registry["supporting_technologies"]
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
                payload["written_to"] = str(args.output)
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0

        if args.command == "atlas-status":
            atlas = json.loads((args.output / "expedition_atlas.json").read_text(encoding="utf-8"))
            chain = verify_visit_chain(atlas)
            print(json.dumps({
                "status": "atlas_valid" if chain["valid"] else "atlas_invalid",
                "map_id": atlas["map_id"],
                "active_location_id": atlas["active_location_id"],
                "mapped_locations": len(atlas["locations"]),
                "routes": len(atlas["routes"]),
                "visits": len(atlas["visits"]),
                "visit_chain_valid": chain["valid"],
                "revisit_options": revisit_options(atlas),
                "atlas_html": str(args.output / "atlas.html"),
            }, indent=2, ensure_ascii=False))
            return 0 if chain["valid"] else 1

        if args.command == "atlas-import-system":
            atlas_path = args.output / "expedition_atlas.json"
            atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
            imported = json.loads(args.system_json.read_text(encoding="utf-8"))
            atlas = register_system_location(atlas, imported, make_active=True)
            atlas = record_visit(
                atlas,
                atlas["active_location_id"],
                event=None,
                visit_kind="imported_campaign_arrival",
                note=args.visit_note,
            )
            write_atlas_files(args.output, atlas)
            manifest = refresh_output_manifest(args.output)
            print(json.dumps({
                "status": "system_registered",
                "active_location_id": atlas["active_location_id"],
                "mapped_locations": len(atlas["locations"]),
                "routes": len(atlas["routes"]),
                "revisit_options": revisit_options(atlas),
                "files": manifest["files"],
            }, indent=2, ensure_ascii=False))
            return 0

        if args.command == "revisit-location":
            atlas_path = args.output / "expedition_atlas.json"
            atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
            packet, atlas = create_revisit_packet(
                atlas,
                location_id=args.location_id,
                visual_engine_version=args.visual_engine_version,
                asset_engine_version=args.asset_engine_version,
                camera_language=args.camera_language,
            )
            packets = args.output / "revisit_packets"
            packets.mkdir(parents=True, exist_ok=True)
            packet_path = packets / f"{packet['packet_id']}.json"
            packet_path.write_text(json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")
            write_atlas_files(args.output, atlas)
            manifest = refresh_output_manifest(args.output)
            print(json.dumps({
                "status": "revisit_packet_created",
                "packet": str(packet_path),
                "packet_sha256": packet["packet_sha256"],
                "history_changed": False,
                "visual_engine_version": args.visual_engine_version,
                "files": manifest["files"],
            }, indent=2, ensure_ascii=False))
            return 0

        if args.command == "atlas-import-catalog":
            atlas_path = args.output / "expedition_atlas.json"
            atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
            snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
            atlas, report = import_normalized_catalog(atlas, snapshot)
            write_atlas_files(args.output, atlas)
            manifest = refresh_output_manifest(args.output)
            print(json.dumps({
                "status": "catalog_snapshot_imported",
                **report,
                "mapped_locations": len(atlas["locations"]),
                "catalog_revisions": len(atlas["catalog_revisions"]),
                "files": manifest["files"],
            }, indent=2, ensure_ascii=False))
            return 0

        if args.command == "create-seed":
            receipt = create_master_seed_receipt(
                args.mode,
                phrase=args.phrase,
                beacon=_read_json(args.beacon_file),
                party_reveals=_read_reveals(args.reveal),
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
            print(json.dumps({"status": "seed_resolved", "resolved_seed": receipt["resolved_seed"], "receipt": str(args.output)}, indent=2))
            return 0

        if args.command == "create-commitment":
            reveal = create_commitment(args.label, args.value)
            args.output.mkdir(parents=True, exist_ok=True)
            public = {"schema": "axm.party-commitment.v1", "label": reveal["label"], "commitment": reveal["commitment"]}
            public_path = args.output / f"{args.label}_public_commitment.json"
            private_path = args.output / f"{args.label}_private_reveal.json"
            public_path.write_text(json.dumps(public, indent=2), encoding="utf-8")
            private_path.write_text(json.dumps(reveal, indent=2), encoding="utf-8")
            print(json.dumps({
                "status": "commitment_created",
                "public_commitment": str(public_path),
                "private_reveal": str(private_path),
                "warning": "Share the public file first. Keep the private reveal hidden until all parties have committed.",
            }, indent=2))
            return 0

        if args.command == "evolve":
            system, state, _ = _load_verified(args.output)
            event, updated = resolve_turn(
                system=system,
                state={**state, "command": {**state.get("command", {}), "pending_session_id": None}},
                action=args.action,
                entropy_mode=args.mode,
                beacon=_read_json(args.beacon_file),
                party_reveals=_read_reveals(args.reveal),
            )
            manifest = append_runtime_event(args.output, event, updated)
            print(json.dumps({
                "status": "event_resolved",
                "turn": event["turn"],
                "action": event["action"],
                "outcome": event["outcome"]["title"],
                "entropy_mode": event["entropy"]["mode"],
                "predetermined_by_master_seed": event["predetermined_by_master_seed"],
                "event_hash": event["event_hash"],
                "files": manifest["files"],
            }, indent=2))
            return 0

        if args.command == "verify-ledger":
            system = json.loads((args.output / "system.json").read_text(encoding="utf-8"))
            valid, checks, _state = verify_ledger(system, load_ledger(args.output / "event_ledger.jsonl"))
            print(json.dumps({"status": "verified" if valid else "failed", "events": len(checks), "valid": valid, "checks": checks}, indent=2))
            return 0 if valid else 1

        if args.command == "fetch-beacon":
            path = fetch_drand_latest(args.output)
            packet = json.loads(path.read_text(encoding="utf-8"))
            print(json.dumps({
                "status": "beacon_saved",
                "path": str(path),
                "verification_status": packet.get("verification_status"),
                "accepted_as_entropy": packet.get("verification_status") == "cryptographically_verified",
            }, indent=2))
            return 0

        if args.command == "verify-beacon":
            packet = json.loads(args.input.read_text(encoding="utf-8"))
            verification = verify_drand_packet(packet)
            if args.write_back:
                packet["verification"] = verification
                packet["verification_status"] = verification["status"]
                args.input.write_text(json.dumps(packet, indent=2), encoding="utf-8")
            print(json.dumps(verification, indent=2))
            return 0 if verification["valid"] else 1

        if args.command == "update-sources":
            if args.source == "nasa_exoplanet_archive":
                path = update_nasa_exoplanet_archive(args.output, args.limit)
            else:
                if not args.query:
                    raise ValueError("--query is required for jpl_sbdb")
                path = update_jpl_sbdb(args.output, args.query)
            print(json.dumps({"status": "snapshot_created", "path": str(path)}, indent=2))
            return 0

        if args.command == "normalize-snapshot":
            result = normalize_nasa_snapshot(args.snapshot, args.output)
            print(json.dumps({"status": "normalized", **result}, indent=2))
            return 0

        if args.command == "summarize-catalog":
            result = summarize_catalog(args.input, args.output)
            print(json.dumps({"status": "summarized", "records": result["records"], "output": str(args.output)}, indent=2))
            return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 2
