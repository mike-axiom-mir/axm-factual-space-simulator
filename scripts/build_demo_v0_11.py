from __future__ import annotations

import json
import shutil
from pathlib import Path

from axm_star_sim.ship_interior import (
    advance_away_operations,
    answer_command_recall,
    create_interior_state,
    move_to_room,
    perform_room_interaction,
    resolve_command_recall,
    validate_interior_archetype,
    verify_interior_state,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "ship_interior_demo"
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)

state = create_interior_state("AXM-FIRST-LIVED-IN-SHIP-DEMO")
state = move_to_room(state, "mess_hall")
state = perform_room_interaction(state, "review_consumable_duration", {
    "crew_count": 6,
    "food_kg": 220,
    "water_liters": 510,
    "food_kg_per_person_day": 0.95,
    "water_liters_per_person_day": 2.1,
})
state = move_to_room(state, "research_strategy")
state = perform_room_interaction(state, "compare_hypotheses", {
    "hypotheses": [
        {
            "hypothesis_id": "instrument_artifact",
            "supporting_channels": 1,
            "independent_replications": 0,
            "controls_passed": 0,
            "contradictions": 1,
            "unresolved_controls": ["independent_sensor"],
        },
        {
            "hypothesis_id": "unusual_atmospheric_chemistry",
            "supporting_channels": 3,
            "independent_replications": 1,
            "controls_passed": 2,
            "contradictions": 0,
            "unresolved_controls": ["abiotic_photochemistry_model"],
        },
    ],
})
state = advance_away_operations(state, 20, {
    "authority_level": "command_required",
    "summary": "A probe detects a rapidly closing object with several reversible and irreversible response options.",
    "reversible": False,
})
state = answer_command_recall(state)
state = resolve_command_recall(
    state,
    "hold_position_and_collect_passive_data",
    "The reversible option preserves safety and evidence while avoiding an unverified approach.",
)
state = move_to_room(state, "engineering")
state = perform_room_interaction(state, "inspect_power_balance", {
    "generation_kw": 60,
    "base_load_kw": 34,
    "active_load_kw": 17,
    "reserve_requirement_kw": 5,
})
state = perform_room_interaction(state, "fabricate_room_item", {
    "item_name": "First anomaly orbit model",
    "material_kg": 0.8,
    "energy_kwh": 2.5,
    "fabrication_hours": 1.5,
    "intended_capability": None,
    "capability_validation": None,
})
new_item_id = state["inventory"][-1]["id"]
state = move_to_room(state, "primary_quarters")
state = perform_room_interaction(state, "display_provenanced_item", {
    "item_id": new_item_id,
    "room_id": "primary_quarters",
    "display_anchor": "shelf_center",
})

(OUT / "demo_state.json").write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
report = {
    "schema": "axm.ship-interior-demo-report.v1",
    "interior_validation": validate_interior_archetype(),
    "state_verification": verify_interior_state(state),
    "current_room": state["current_room_id"],
    "rooms_visited": [row["room_id"] for row in state["room_visit_history"]],
    "fabricated_item_id": new_item_id,
    "routine_events": len(state["routine_events_resolved"]),
    "interactions": len(state["interaction_history"]),
}
(OUT / "demo_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(report, indent=2, ensure_ascii=False))

# Restore the canonical visual entry page after deterministic data rebuild.
_template = ROOT / "assets" / "demo_templates" / "ship_interior_console.html"
(OUT / "ship_interior_console.html").write_text(_template.read_text(encoding="utf-8"), encoding="utf-8")
