from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from axm_star_sim.adventure_slots import (
    forge_external_ai_assisted_scenario,
    forge_offline_base_scenario,
    prepare_external_forge_request_data,
)
from axm_star_sim.blind_forge import scan_public_bundle_for_private_leaks, verify_private_reveal
from axm_star_sim.generator import generate_system

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "stress_report_v0_9_0.json"
OFFLINE_SYSTEMS = 140
EXTERNAL_SYSTEMS = 80

offline_candidates = Counter()
external_candidates = Counter()
commitments = set()
failures = []

for index in range(OFFLINE_SYSTEMS):
    system = generate_system(f"AXM-V09-OFFLINE-WORLD-{index:04d}").to_dict()
    private, public = forge_offline_base_scenario(system, f"AXM-V09-OFFLINE-FORGE-{index:04d}")
    offline_candidates[private["reasoned_candidate_matrix"]["selected_candidate_id"]] += 1
    commitments.add(public["private_scenario_commitment_sha256"])
    if scan_public_bundle_for_private_leaks(public, private):
        failures.append({"mode": "offline", "index": index, "error": "public leak"})
    if not verify_private_reveal(private, public)["valid"]:
        failures.append({"mode": "offline", "index": index, "error": "commitment failure"})

for index in range(EXTERNAL_SYSTEMS):
    world_seed = f"AXM-V09-EXTERNAL-WORLD-{index:04d}"
    forge_seed = f"AXM-V09-EXTERNAL-FORGE-{index:04d}"
    system = generate_system(world_seed).to_dict()
    request = prepare_external_forge_request_data(system, forge_seed)
    selected = request["candidate_shortlist"][index % len(request["candidate_shortlist"])]
    proposal = {
        "schema": "axm.external-ai-forge-proposal.v1",
        "request_id": request["request_id"],
        "proposal_author": f"Stress proposal seat {index}",
        "preferred_anomaly_family_ids": [selected["anomaly_family_id"]],
        "preferred_life_architecture_ids": [selected["life_architecture_id"]],
        "emphasis_observable_ids": [],
        "investigation_emphasis": ["balanced", "falsification_first", "anomaly_hunting", "conservative"][index % 4],
        "rationale_summary": ["Structured proposal without hidden-outcome authority."],
        "proposal_nonce": str(index),
    }
    private, public = forge_external_ai_assisted_scenario(system, forge_seed, proposal)
    external_candidates[private["reasoned_candidate_matrix"]["selected_candidate_id"]] += 1
    commitments.add(public["private_scenario_commitment_sha256"])
    if scan_public_bundle_for_private_leaks(public, private):
        failures.append({"mode": "external", "index": index, "error": "public leak"})
    if not verify_private_reveal(private, public)["valid"]:
        failures.append({"mode": "external", "index": index, "error": "commitment failure"})
    if public["adventure_slot_start"]["external_connection_required_after_creation"]:
        failures.append({"mode": "external", "index": index, "error": "external dependency remained active"})

control_system = generate_system("AXM-V09-DETERMINISM-CONTROL").to_dict()
a_private, a_public = forge_offline_base_scenario(control_system, "AXM-V09-DETERMINISM-FORGE")
b_private, b_public = forge_offline_base_scenario(control_system, "AXM-V09-DETERMINISM-FORGE")
deterministic = (
    a_private == b_private
    and a_public == b_public
    and a_public["private_scenario_commitment_sha256"] == b_public["private_scenario_commitment_sha256"]
)

report = {
    "schema": "axm.v0.9-slot-forge-stress.v1",
    "offline_systems": OFFLINE_SYSTEMS,
    "external_assisted_systems": EXTERNAL_SYSTEMS,
    "total_unique_commitments": len(commitments),
    "offline_distinct_candidates": len(offline_candidates),
    "external_distinct_candidates": len(external_candidates),
    "offline_candidate_counts": dict(offline_candidates),
    "external_candidate_counts": dict(external_candidates),
    "offline_determinism_control": deterministic,
    "external_connection_required_after_creation": False,
    "failures": failures,
    "valid": not failures and deterministic and len(commitments) == OFFLINE_SYSTEMS + EXTERNAL_SYSTEMS,
}
REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(report, indent=2, ensure_ascii=False))
raise SystemExit(0 if report["valid"] else 1)
