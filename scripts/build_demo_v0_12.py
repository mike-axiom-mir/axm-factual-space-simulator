from __future__ import annotations

import json
import shutil
from pathlib import Path

from axm_star_sim.generator import generate_system
from axm_star_sim.runtime import initial_runtime_state
from axm_star_sim.command import crew_assessment
from axm_star_sim.rooted_crew import (
    evolve_derived_principles,
    generate_principled_options,
    load_default_crew,
    load_root_kernel,
    verify_derived_principles,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "rooted_crew_demo"
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)

farmer_case = generate_principled_options(
    "obtain a missing repair tool",
    [
        {
            "candidate_id": "armed_robbery",
            "label": "Threaten a nearby worker and take the tool",
            "evidence_status": "known",
            "takes_property_without_consent": True,
            "coercive": True,
            "destructive_shortcut": True,
            "legitimate_alternatives": ["borrow", "repair", "trade", "fabricate"],
            "immediate_utility": 1.0,
            "long_term_utility": 0.05,
            "systemic_damage": 0.95,
            "efficiency": 1.0,
        },
        {
            "candidate_id": "borrow_and_repair",
            "label": "Ask to borrow the tool and offer repair work",
            "evidence_status": "known",
            "consent_required": True,
            "consent_status": "granted",
            "role_authorized": True,
            "recovery_path": True,
            "immediate_utility": 0.60,
            "long_term_utility": 0.90,
            "learning_value": 0.25,
            "repair_value": 0.80,
            "proportionality": 1.0,
            "systemic_damage": 0.0,
            "efficiency": 0.58,
        },
        {
            "candidate_id": "fabricate_simple_tool",
            "label": "Fabricate a slower temporary tool from available material",
            "evidence_status": "bounded_unknown",
            "recovery_path": True,
            "role_authorized": True,
            "immediate_utility": 0.48,
            "long_term_utility": 0.76,
            "learning_value": 0.72,
            "repair_value": 0.55,
            "proportionality": 0.95,
            "systemic_damage": 0.05,
            "efficiency": 0.42,
        },
    ],
    {"world": "generic persistent settlement", "lesson": "local efficiency is not complete rationality"},
)

kernel = load_root_kernel()
evolution = evolve_derived_principles(
    {},
    [
        {
            "principle_id": "shared_resource_request_first",
            "statement": "Request or negotiate shared-resource use before considering unilateral control.",
            "derived_from_roots": ["agency_no_takeover", "wisdom_over_speed"],
            "evidence_or_lesson_receipts": [farmer_case["generation_receipt"]],
            "status": "working",
        },
        {
            "principle_id": "preserve_original_measurements",
            "statement": "Keep original measurements before filtering, transforming, or summarizing them.",
            "derived_from_roots": ["truth_source_truth", "continuity_no_loss"],
            "evidence_or_lesson_receipts": ["measurement-provenance-lesson"],
            "status": "working",
        },
    ],
    kernel["root_commitment_sha256"],
)

system = generate_system("AXM-V012-ROOTED-CREW-DEMO").to_dict()
state = initial_runtime_state(system)
assessment = crew_assessment(system, state)

report = {
    "schema": "axm.rooted-crew-demo.v1",
    "root_kernel": kernel,
    "default_crew": load_default_crew(),
    "farmer_case": farmer_case,
    "derived_evolution": evolution,
    "derived_evolution_verification": verify_derived_principles(evolution),
    "live_crew_assessment": assessment,
}
(OUT / "rooted_crew_demo.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({
    "root_commitment": kernel["root_commitment_sha256"],
    "farmer_recommendation": farmer_case["recommended_option_id"],
    "rejected_shortcuts": len(farmer_case["rejected_options"]),
    "derived_principles": len(evolution["derived_principles"]),
    "crew_recommendation": assessment["recommended_action"],
}, indent=2))

# Restore the canonical visual entry page after deterministic data rebuild.
_template = ROOT / "assets" / "demo_templates" / "rooted_crew_console.html"
(OUT / "rooted_crew_console.html").write_text(_template.read_text(encoding="utf-8"), encoding="utf-8")
