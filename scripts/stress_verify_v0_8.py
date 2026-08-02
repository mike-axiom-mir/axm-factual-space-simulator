from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from axm_star_sim.blind_forge import (
    ACTION_CATALOG,
    forge_blind_scenario,
    resolve_blind_action,
    scan_public_bundle_for_private_leaks,
    verify_private_reveal,
    verify_session,
)
from axm_star_sim.cosmic_possibility import validate_cosmic_possibility_registry
from axm_star_sim.generator import generate_system

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "stress_report_v0_8_0.json"
SYSTEMS = 300
TURNS = 10

origin_counts = Counter()
anomaly_counts = Counter()
architecture_counts = Counter()
outcome_counts = Counter()
max_stage_counts = Counter()
selected_pairs = Counter()
leak_failures = []
replay_failures = []

for index in range(SYSTEMS):
    world_seed = f"AXM-V08-STRESS-WORLD-{index:04d}"
    forge_seed = f"AXM-V08-STRESS-FORGE-{index:04d}"
    system = generate_system(world_seed).to_dict()
    private_payload, public_bundle = forge_blind_scenario(system, forge_seed)
    leaks = scan_public_bundle_for_private_leaks(public_bundle, private_payload)
    if leaks:
        leak_failures.append({"index": index, "leaks": leaks})
    reveal = verify_private_reveal(private_payload, public_bundle)
    if not reveal["valid"]:
        replay_failures.append({"index": index, "phase": "commitment", "result": reveal})
        continue
    truth = private_payload["private_simulation_truth"]
    origin_counts[truth["origin_class"]] += 1
    anomaly_counts[private_payload["selected_anomaly_family"]["id"]] += 1
    architecture_counts[private_payload["selected_life_architecture"]["id"]] += 1
    selected_pairs[private_payload["reasoned_candidate_matrix"]["selected_candidate_id"]] += 1
    state = public_bundle["initial_state"]
    events = []
    tokens = []
    max_stage = 0
    for turn in range(TURNS):
        action = ACTION_CATALOG[(index + turn * 3) % len(ACTION_CATALOG)]["id"]
        if action == "move_on_preserve_candidate" and turn < TURNS - 1:
            action = "repeat_changed_geometry"
        token = f"STRESS-ENTROPY-{index:04d}-{turn:02d}"
        event, state = resolve_blind_action(private_payload, public_bundle, state, action, token)
        events.append(event)
        tokens.append(token)
        outcome_counts[event["observation"]["outcome_class"]] += 1
        max_stage = max(max_stage, int(state["evidence_stage"]))
        if state["status"] != "active":
            break
    max_stage_counts[max_stage] += 1
    verified = verify_session(private_payload, public_bundle, events, tokens)
    if not verified["valid"]:
        replay_failures.append({"index": index, "phase": "events", "result": verified})

# Same world, multiple independent forge seeds must preserve the world while producing more than one private lens.
control_system = generate_system("AXM-V08-SAME-WORLD-CONTROL").to_dict()
control_commitments = set()
control_pairs = set()
for index in range(40):
    private_payload, public_bundle = forge_blind_scenario(control_system, f"AXM-CONTROL-FORGE-{index}")
    control_commitments.add(public_bundle["private_scenario_commitment_sha256"])
    control_pairs.add(private_payload["reasoned_candidate_matrix"]["selected_candidate_id"])

report = {
    "schema": "axm.v0.8-stress-report.v1",
    "systems": SYSTEMS,
    "events_attempted": SYSTEMS * TURNS,
    "registry_errors": validate_cosmic_possibility_registry(),
    "origin_counts": dict(origin_counts),
    "anomaly_counts": dict(anomaly_counts),
    "architecture_counts": dict(architecture_counts),
    "outcome_counts": dict(outcome_counts),
    "max_stage_counts": {str(key): value for key, value in sorted(max_stage_counts.items())},
    "distinct_selected_pairs": len(selected_pairs),
    "same_world_distinct_private_commitments": len(control_commitments),
    "same_world_distinct_theory_pairs": len(control_pairs),
    "public_leak_failures": leak_failures,
    "replay_failures": replay_failures,
    "valid": (
        not validate_cosmic_possibility_registry()
        and not leak_failures
        and not replay_failures
        and len(origin_counts) == 7
        and len(anomaly_counts) >= 5
        and len(architecture_counts) >= 8
        and len(control_commitments) == 40
        and len(control_pairs) > 1
    ),
}
REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(report, indent=2, ensure_ascii=False))
raise SystemExit(0 if report["valid"] else 1)
