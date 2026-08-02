from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from axm_star_sim.ship_blueprint import (
    advance_ship_state,
    apply_encounter_effects,
    apply_failure_mode,
    create_ship_state,
    evaluate_ship,
    role_perspective_snapshot,
    verify_ship_state,
)

ROOT = Path(__file__).resolve().parents[1]
FAILURES = [
    "power_generation_degraded", "radiator_capacity_loss", "cabin_pressure_leak",
    "co2_removal_degraded", "water_recovery_degraded", "cdh_channel_fault",
    "navigation_sensor_disagreement", "communications_pointing_loss",
    "radiation_event", "mmod_impact",
]
ROLES = [
    "mission_commander", "ai_systems_integrator", "flight_dynamics_navigation",
    "vehicle_systems_engineer", "science_anomaly_specialist",
    "communications_data_robotics", "crew_medical_officer",
]

states = 260
failures = []
mode_counts = Counter()
recalls = 0
role_snapshots = 0

for index in range(states):
    state = create_ship_state(f"AXM-V013-STRESS-{index:04d}")
    state = advance_ship_state(
        state,
        30 + (index % 90),
        solar_flux_ratio=0.0 if index % 17 == 0 else 0.65 + (index % 35) / 100.0,
        data_generated_gb=float(index % 12),
    )
    state = apply_encounter_effects(state, {
        "encounter_id": f"stress-encounter-{index}",
        "summary": "Deterministic multi-system encounter stress packet",
        "effects": {
            "kinetic_impact_index": float(index % 7),
            "external_thermal_load_kw": float(index % 9),
            "radiation_index_delta": float(index % 5) * 0.7,
            "electromagnetic_interference_fraction": float(index % 6) * 0.08,
            "navigation_uncertainty_km_delta": float(index % 11) * 0.4,
            "power_generation_loss_fraction": float(index % 4) * 0.05,
            "data_integrity_risk_fraction": float(index % 5) * 0.06,
        },
    })
    state = apply_failure_mode(state, FAILURES[index % len(FAILURES)])
    state = advance_ship_state(state, 15)
    verification = verify_ship_state(state)
    if not verification["valid"]:
        failures.append({"index": index, "verification": verification})
    evaluation = evaluate_ship(state)
    mode_counts[evaluation["mode"]] += 1
    if evaluation["command"]["pending_recall"] is not None:
        recalls += 1
    for role_id in ROLES:
        snapshot = role_perspective_snapshot(state, role_id)
        role_snapshots += 1
        if snapshot["ship_state_hash"] != state["state_hash"]:
            failures.append({"index": index, "role": role_id, "error": "role state hash mismatch"})

report = {
    "schema": "axm.factual-ship-blueprint-stress.v1",
    "states": states,
    "encounters": states,
    "injected_failures": states,
    "role_snapshots": role_snapshots,
    "command_recalls": recalls,
    "mode_counts": dict(mode_counts),
    "failures": failures,
    "valid": not failures,
}
(ROOT / "docs" / "stress_report_v0_13_0.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["valid"] else 1)
