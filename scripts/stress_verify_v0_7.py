from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path

from axm_star_sim.atlas import (
    build_expedition_atlas,
    create_revisit_packet,
    record_visit,
    register_system_location,
    validate_atlas_sources,
    verify_visit_chain,
)
from axm_star_sim.generator import generate_system
from axm_star_sim.runtime import initial_runtime_state, resolve_turn, verify_recorded_event


def main() -> int:
    validate_atlas_sources()
    systems = 240
    turns_per_system = 10
    merge_pairs = 60
    verified_events = 0
    verified_visit_chains = 0
    knowledge_classes: Counter[str] = Counter()
    min_distance = float("inf")
    max_distance = 0.0
    reference_hashes = None

    for index in range(systems):
        seed = f"AXM-V07-ATLAS-STRESS-{index:04d}"
        system = generate_system(seed).to_dict()
        atlas = build_expedition_atlas(system, created_at="2026-08-02T00:00:00Z")
        real_hashes = {
            location_id: atlas["locations"][location_id]["authoritative_snapshot_sha256"]
            for location_id in ("catalog:sol", "catalog:proxima-centauri", "catalog:trappist-1", "catalog:51-pegasi")
        }
        if reference_hashes is None:
            reference_hashes = real_hashes
        elif real_hashes != reference_hashes:
            raise AssertionError({"seed": seed, "error": "real landmark changed with seed"})

        active = atlas["locations"][atlas["active_location_id"]]
        if active["knowledge_class"] != "procedural_frontier":
            raise AssertionError({"seed": seed, "error": "frontier mislabeled"})
        if active["coordinates"]["truth_type"] != "simulation_prior":
            raise AssertionError({"seed": seed, "error": "frontier coordinate promoted"})
        distance = float(active["distance_ly"]["value"])
        min_distance = min(min_distance, distance)
        max_distance = max(max_distance, distance)
        for location in atlas["locations"].values():
            knowledge_classes[location["knowledge_class"]] += 1

        state = initial_runtime_state(system)
        for turn in range(turns_per_system):
            actions = state["action_menu"]["actions"]
            action = actions[(index + turn * 2) % len(actions)]["action_id"]
            event, updated = resolve_turn(system=system, state=state, action=action, entropy_mode="deterministic")
            check, rebuilt = verify_recorded_event(system, state, event)
            if not check["valid"] or rebuilt != updated:
                raise AssertionError({"seed": seed, "turn": turn + 1, "event_check": check})
            atlas = record_visit(
                atlas,
                atlas["active_location_id"],
                event,
                visited_at=f"2026-08-02T00:{turn:02d}:00Z",
            )
            chain = verify_visit_chain(atlas)
            if not chain["valid"]:
                raise AssertionError({"seed": seed, "turn": turn + 1, "visit_chain": chain})
            verified_events += 1
            state = updated
        verified_visit_chains += 1

    revisit_packets = 0
    merged_routes = 0
    for index in range(merge_pairs):
        system_a = generate_system(f"AXM-V07-MERGE-A-{index:03d}").to_dict()
        system_b = generate_system(f"AXM-V07-MERGE-B-{index:03d}").to_dict()
        atlas = build_expedition_atlas(system_a, created_at="2026-08-02T00:00:00Z")
        old_location = atlas["active_location_id"]
        old_visit_head = atlas["visit_chain_head"]
        atlas = register_system_location(atlas, system_b, make_active=True)
        atlas = record_visit(
            atlas,
            atlas["active_location_id"],
            event=None,
            visit_kind="stress_merge_arrival",
            visited_at="2026-08-02T01:00:00Z",
        )
        if atlas["routes"][-1]["feasibility"] != "resolved_by_event_ledger_not_coordinate_map":
            raise AssertionError({"pair": index, "error": "route line promoted to capability"})
        packet, atlas = create_revisit_packet(
            atlas,
            old_location,
            visual_engine_version=f"future-visual-{index % 5}",
            asset_engine_version=f"future-assets-{index % 7}",
            created_at="2035-01-01T00:00:00Z",
        )
        if packet["authoritative_location_snapshot_sha256"] != atlas["locations"][old_location]["authoritative_snapshot_sha256"]:
            raise AssertionError({"pair": index, "error": "revisit changed location authority"})
        # One arrival visit was legitimately appended during the merge. Rendering itself must not add another visit.
        if atlas["visit_chain_head"] == old_visit_head:
            raise AssertionError({"pair": index, "error": "merge visit was not recorded"})
        before_render_chain = atlas["visit_chain_head"]
        packet2, atlas = create_revisit_packet(
            atlas,
            old_location,
            visual_engine_version=f"future-visual-{index % 5}-upgrade",
            asset_engine_version=f"future-assets-{index % 7}-upgrade",
            created_at="2040-01-01T00:00:00Z",
        )
        if atlas["visit_chain_head"] != before_render_chain:
            raise AssertionError({"pair": index, "error": "render revision mutated visit chain"})
        if packet["packet_sha256"] == packet2["packet_sha256"]:
            raise AssertionError({"pair": index, "error": "different render requests collapsed"})
        if not verify_visit_chain(atlas)["valid"]:
            raise AssertionError({"pair": index, "error": "merged visit chain invalid"})
        revisit_packets += 2
        merged_routes += 1

    result = {
        "schema": "axm.v0.7-atlas-stress-report.v1",
        "status": "PASS",
        "systems": systems,
        "turns_per_system": turns_per_system,
        "events_replay_verified": verified_events,
        "visit_chains_verified": verified_visit_chains,
        "real_landmark_hashes_stable_across_seeds": True,
        "frontier_coordinates_promoted_to_catalog_fact": False,
        "frontier_distance_range_ly": {"minimum": round(min_distance, 6), "maximum": round(max_distance, 6)},
        "knowledge_classes_observed": dict(sorted(knowledge_classes.items())),
        "multi_system_merge_pairs": merge_pairs,
        "merged_routes": merged_routes,
        "revisit_packets_verified": revisit_packets,
        "render_revisions_mutated_visit_history": False,
        "route_lines_promoted_to_ship_capability": False,
    }
    root = Path(__file__).resolve().parents[1]
    path = root / "docs" / "stress_report_v0_7_0.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
