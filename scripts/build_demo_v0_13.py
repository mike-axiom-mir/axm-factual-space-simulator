from __future__ import annotations

import json
import shutil
from pathlib import Path

from axm_star_sim.ship_blueprint import (
    advance_ship_state,
    apply_encounter_effects,
    apply_failure_mode,
    blueprint_commitment,
    create_ship_state,
    evaluate_ship,
    fault_propagation_paths,
    qualification_gap_plan,
    role_perspective_snapshot,
    validate_blueprint,
    verify_ship_state,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "factual_ship_blueprint_demo"
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)

state = create_ship_state("AXM-FIRST-COMPLETE-SHIP-BLUEPRINT")
initial_evaluation = evaluate_ship(state)
state = advance_ship_state(
    state,
    45,
    activity_loads_kw={
        "external_sensors": 8.0,
        "science_payload_and_analysis": 7.0,
        "robotics_and_probe_operations": 5.0,
    },
    data_generated_gb=18.0,
)
state = apply_encounter_effects(state, {
    "encounter_id": "UNRESOLVED-CLOSE-APPROACH-001",
    "summary": "An unresolved object passes close enough to create sensor ambiguity, heating, and a small impact signature.",
    "observations": [
        "optical track",
        "radio noise rise",
        "brief exterior impact acoustic event",
        "no validated intent signal",
    ],
    "declared_intent": "unknown",
    "effects": {
        "kinetic_impact_index": 2.8,
        "external_thermal_load_kw": 6.0,
        "electromagnetic_interference_fraction": 0.25,
        "navigation_uncertainty_km_delta": 4.0,
        "data_integrity_risk_fraction": 0.15,
    },
})
state = apply_failure_mode(state, "navigation_sensor_disagreement")
state = advance_ship_state(state, 20, data_generated_gb=4.0)

role_ids = (
    "mission_commander",
    "ai_systems_integrator",
    "flight_dynamics_navigation",
    "vehicle_systems_engineer",
    "science_anomaly_specialist",
    "communications_data_robotics",
    "crew_medical_officer",
)
roles = {role_id: role_perspective_snapshot(state, role_id) for role_id in role_ids}
qualification_plan = qualification_gap_plan(
    state,
    "communications_data_robotics",
    {"robotics_and_probe_operations": 5, "gnc": 3},
)

report = {
    "schema": "axm.factual-ship-blueprint-demo.v1",
    "blueprint_validation": validate_blueprint(),
    "blueprint_commitment": blueprint_commitment(),
    "initial_evaluation": initial_evaluation,
    "final_evaluation": evaluate_ship(state),
    "state_verification": verify_ship_state(state),
    "role_perspectives": roles,
    "qualification_gap_plan": qualification_plan,
    "power_fault_paths": fault_propagation_paths("electrical_power_generation"),
    "honest_boundary": {
        "flight_certified": False,
        "complete_mass_known": False,
        "verified_delta_v_known": False,
        "system_architecture_complete_for_simulation": True,
        "encounter_intent_inferred_from_damage": False,
    },
}
(OUT / "ship_state.json").write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
(OUT / "demo_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({
    "blueprint_valid": report["blueprint_validation"]["valid"],
    "systems": report["blueprint_validation"]["system_count"],
    "interfaces": report["blueprint_validation"]["interface_count"],
    "failure_modes": report["blueprint_validation"]["failure_mode_count"],
    "state_valid": report["state_verification"]["valid"],
    "faults": report["state_verification"]["fault_count"],
    "encounters": report["state_verification"]["encounter_count"],
    "command_recall": report["final_evaluation"]["command"]["pending_recall"] is not None,
}, indent=2))


# Restore the canonical visual entry page after deterministic data rebuild.
_template = ROOT / "assets" / "demo_templates" / "ship_blueprint_console.html"
(OUT / "ship_blueprint_console.html").write_text(_template.read_text(encoding="utf-8"), encoding="utf-8")
