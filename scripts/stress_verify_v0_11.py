from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from axm_star_sim.ship_interior import (
    advance_away_operations,
    answer_command_recall,
    create_interior_state,
    move_to_room,
    perform_room_interaction,
    resolve_command_recall,
    verify_interior_state,
)

ROOT = Path(__file__).resolve().parents[1]
ROOMS = ["mess_hall", "engineering", "research_strategy", "primary_quarters", "collaborator_quarters"]
room_counts = Counter()
recalls = 0
failures = []
states = 180

for index in range(states):
    state = create_interior_state(f"AXM-V011-STRESS-{index:04d}")
    for turn in range(12):
        room = ROOMS[(index + turn) % len(ROOMS)]
        state = move_to_room(state, room)
        room_counts[room] += 1
        if room == "mess_hall":
            state = perform_room_interaction(state, "review_consumable_duration", {
                "crew_count": 6,
                "food_kg": 180 + index % 30,
                "water_liters": 360 + index % 50,
                "food_kg_per_person_day": 1.0,
                "water_liters_per_person_day": 2.0,
            })
        elif room == "engineering":
            state = perform_room_interaction(state, "inspect_power_balance", {
                "generation_kw": 60,
                "base_load_kw": 33 + turn % 3,
                "active_load_kw": 12 + turn % 5,
                "reserve_requirement_kw": 5,
            })
        elif room == "research_strategy":
            state = perform_room_interaction(state, "compare_hypotheses", {
                "hypotheses": [
                    {"hypothesis_id":"natural_process","supporting_channels":2,"independent_replications":1,"controls_passed":2,"contradictions":0,"unresolved_controls":["geometry_change"]},
                    {"hypothesis_id":"instrument_artifact","supporting_channels":1,"independent_replications":0,"controls_passed":0,"contradictions":1,"unresolved_controls":["independent_hardware"]}
                ]
            })
        elif room == "collaborator_quarters":
            state = perform_room_interaction(state, "offline_alternative_review", {
                "case_id": f"CASE-{index}-{turn}",
                "known_evidence": ["unresolved periodic variation"],
                "known_alternatives": ["instrument interference", "natural process"],
            })
        if turn in {4, 9}:
            state = advance_away_operations(state, 5, {
                "authority_level": "command_required",
                "summary": "Stress command recall",
                "reversible": False,
            })
            recalls += 1
            state = answer_command_recall(state)
            state = resolve_command_recall(state, "hold_reversible_posture", "Stress verification.")
    verification = verify_interior_state(state)
    if not verification["valid"]:
        failures.append({"index": index, "verification": verification})

report = {
    "schema": "axm.ship-interior-stress.v1",
    "states": states,
    "room_visits": dict(room_counts),
    "command_recalls_resolved": recalls,
    "failures": failures,
    "valid": not failures,
}
(ROOT / "docs" / "stress_report_v0_11_0.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["valid"] else 1)
