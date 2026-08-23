from __future__ import annotations

import json
from pathlib import Path

from axm_star_sim.living_operations_bridge import enrich_storyboard
from axm_star_sim.living_operations_bridge_view import render_living_bridge
from axm_star_sim.temporal_renderer_adapter import build_temporal_storyboard, load_verified_snapshot

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "output" / "persistent_atlas_demo" / "expedition_alpha"
OUTPUT = ROOT / "output" / "living_operations_bridge_candidate" / "living_operations_bridge_demo.html"


def _load_data(name: str) -> dict:
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def main() -> int:
    snapshot = load_verified_snapshot(
        system_bytes=(SOURCE / "system.json").read_bytes(),
        runtime_bytes=(SOURCE / "runtime_state.json").read_bytes(),
        event_ledger_bytes=(SOURCE / "event_ledger.jsonl").read_bytes(),
        manifest_bytes=(SOURCE / "manifest.json").read_bytes(),
        source_repository="mike-axiom-mir/axm-factual-space-simulator",
        source_commit="96944abe2ddfd96107a9ef167ff52f80e8d3986d",
    )
    failure_registry = _load_data("ship_failure_mode_registry.json")
    station_registry = _load_data("crew_station_display_registry.json")
    blueprint_registry = _load_data("ship_system_blueprint_registry.json")
    interface_graph = _load_data("ship_interface_graph.json")
    interior_registry = _load_data("ship_interior_archetype_registry.json")
    room_interaction_registry = _load_data("room_interaction_registry.json")

    base_board = build_temporal_storyboard(snapshot)
    board = enrich_storyboard(
        base_board,
        snapshot["runtime"],
        failure_registry=failure_registry,
        station_registry=station_registry,
        blueprint_registry=blueprint_registry,
        interface_graph=interface_graph,
        interior_registry=interior_registry,
        room_interaction_registry=room_interaction_registry,
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render_living_bridge(board, snapshot["import_receipt"]), encoding="utf-8")

    procedures = board["failure_procedures"]
    topology = board["damage_topology"]
    available_access = sum(
        1
        for row in topology["topologies"]
        if str(row.get("access", {}).get("status", "")).startswith("ACCESS_PATH_AVAILABLE")
    )
    print(json.dumps({
        "schema":"axm.living-operations-bridge-repo-build.v4",
        "version":"0.6.0-candidate",
        "source_turn":board["operations_context"]["source_turn"],
        "open_threads":board["operations_context"]["open_thread_count"],
        "available_actions":board["operations_context"]["available_action_count"],
        "rehearsals":board["bridge_rehearsal"]["rehearsal_count"],
        "failure_procedures":procedures["procedure_count"],
        "damage_topologies":topology["topology_count"],
        "mapped_access_topologies":available_access,
        "component_specificity":topology["component_specificity"],
        "procedure_execution_authority":procedures["may_execute_response"],
        "repair_execution_authority":topology["may_execute_repair"],
        "spares_consumption_authority":topology["may_consume_spares"],
        "fault_clear_authority":topology["may_clear_fault"],
        "authority":"presentation_procedure_and_derived_topology_review_only",
        "output":str(OUTPUT.relative_to(ROOT)),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
