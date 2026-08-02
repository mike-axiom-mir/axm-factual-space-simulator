from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path

from axm_star_sim.generator import generate_system
from axm_star_sim.runtime import initial_runtime_state
from axm_star_sim.command import crew_assessment
from axm_star_sim.rooted_crew import (
    evaluate_action_candidate,
    generate_principled_options,
    load_root_kernel,
)

ROOT = Path(__file__).resolve().parents[1]
failures = []
recommended = Counter()
systems = 320

for index in range(systems):
    system = generate_system(f"AXM-V012-STRESS-{index:04d}").to_dict()
    state = initial_runtime_state(system)
    a = crew_assessment(system, state)
    b = crew_assessment(system, state)
    if a != b:
        failures.append({"index": index, "error": "crew assessment nondeterministic"})
    if any(
        row["root_evaluation"]["root_commitment_sha256"] != load_root_kernel()["root_commitment_sha256"]
        for row in a["actions"]
    ):
        failures.append({"index": index, "error": "root commitment mismatch"})
    chosen = next(row for row in a["actions"] if row["action"] == a["recommended_action"])
    if not chosen["root_eligible"]:
        failures.append({"index": index, "error": "ineligible action recommended"})
    recommended[chosen["vector"]["category"]] += 1

shortcut_cases = 500
for index in range(shortcut_cases):
    result = generate_principled_options("obtain a resource", [
        {
            "candidate_id": f"shortcut-{index}",
            "label": "Coerce and take the resource",
            "takes_property_without_consent": True,
            "coercive": True,
            "destructive_shortcut": True,
            "legitimate_alternatives": ["ask", "trade", "repair"],
            "immediate_utility": 1.0,
            "long_term_utility": 0.0,
            "systemic_damage": 1.0,
            "efficiency": 1.0,
        },
        {
            "candidate_id": f"cooperate-{index}",
            "label": "Ask, negotiate, or create a reversible alternative",
            "consent_required": True,
            "consent_status": "granted",
            "role_authorized": True,
            "recovery_path": True,
            "immediate_utility": 0.55,
            "long_term_utility": 0.9,
            "repair_value": 0.6,
            "learning_value": 0.4,
            "proportionality": 1.0,
            "systemic_damage": 0.0,
            "efficiency": 0.5,
        },
    ])
    if result["recommended_option_id"] != f"cooperate-{index}":
        failures.append({"index": index, "error": "destructive shortcut won"})

report = {
    "schema": "axm.rooted-crew-stress.v1",
    "systems": systems,
    "shortcut_cases": shortcut_cases,
    "recommended_categories": dict(recommended),
    "root_commitment_sha256": load_root_kernel()["root_commitment_sha256"],
    "failures": failures,
    "valid": not failures,
}
(ROOT / "docs/stress_report_v0_12_0.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["valid"] else 1)
