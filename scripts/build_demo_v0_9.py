from __future__ import annotations

import json
import shutil
from pathlib import Path

from axm_star_sim.adventure_slots import (
    act_in_adventure_slot,
    create_adventure_slot,
    export_player_bundle,
    list_adventure_slots,
    prepare_external_forge_request,
    verify_adventure_slot,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "adventure_slot_demo"
SLOTS = OUTPUT / "slots"

if OUTPUT.exists():
    shutil.rmtree(OUTPUT)
SLOTS.mkdir(parents=True)

request_path = OUTPUT / "external_ai_forge_request.json"
request = prepare_external_forge_request(
    "MIKE-AXIOM-MIR-SLOT-WORLD-EXTERNAL",
    "MIKE-AXIOM-MIR-SLOT-FORGE-EXTERNAL",
    request_path,
)
first = request["candidate_shortlist"][0]
proposal = {
    "schema": "axm.external-ai-forge-proposal.v1",
    "request_id": request["request_id"],
    "proposal_author": "Example disconnected pre-play reasoning seat",
    "preferred_anomaly_family_ids": [first["anomaly_family_id"]],
    "preferred_life_architecture_ids": [first["life_architecture_id"]],
    "emphasis_observable_ids": [],
    "investigation_emphasis": "falsification_first",
    "rationale_summary": [
        "Prefer a candidate with multiple observables and explicit natural controls.",
        "Do not decide whether the hidden origin is living, abiotic, instrumental, or novel physics.",
    ],
    "proposal_nonce": "AXM-V09-DEMO",
}
proposal_path = OUTPUT / "external_ai_forge_proposal_example.json"
proposal_path.write_text(json.dumps(proposal, indent=2, ensure_ascii=False), encoding="utf-8")

offline = create_adventure_slot(
    SLOTS,
    "offline-foundation",
    "Offline Foundation Expedition",
    "MIKE-AXIOM-MIR-SLOT-WORLD-OFFLINE",
    "MIKE-AXIOM-MIR-SLOT-FORGE-OFFLINE",
    "offline_base",
)
external = create_adventure_slot(
    SLOTS,
    "optional-ai-forged",
    "Optional AI-Forged Expedition",
    "MIKE-AXIOM-MIR-SLOT-WORLD-EXTERNAL",
    "MIKE-AXIOM-MIR-SLOT-FORGE-EXTERNAL",
    "external_ai_assisted",
    proposal=proposal,
)
act_in_adventure_slot(SLOTS, "offline-foundation", "broad_spectrum_survey", "V09-OFFLINE-DEMO-TOKEN")
act_in_adventure_slot(SLOTS, "optional-ai-forged", "abiotic_control_campaign", "V09-EXTERNAL-DEMO-TOKEN")
offline_export = export_player_bundle(SLOTS, "offline-foundation")
external_export = export_player_bundle(SLOTS, "optional-ai-forged")

rows = list_adventure_slots(SLOTS)
cards = "".join(
    f"<article><h2>{row['display_name']}</h2><p><strong>{row['forge_mode']}</strong></p>"
    f"<p>{row['system_name']}</p><p>Turn {row['turn']} · evidence stage {row['evidence_stage']}</p>"
    f"<p>No external connection required after creation.</p></article>"
    for row in rows
)
html = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>AXM Adventure Save Slots</title><style>
:root{{color-scheme:dark;--bg:#061017;--panel:#0d1b24;--line:#294a59;--text:#eef8fa;--muted:#9eb6bd;--accent:#80dfcf}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at top,#173440,var(--bg) 45%);color:var(--text);font-family:system-ui,sans-serif}}
main{{max-width:1000px;margin:auto;padding:28px}}.eyebrow{{color:var(--accent);letter-spacing:.16em;text-transform:uppercase}}
h1{{font-size:clamp(2rem,5vw,3.5rem)}}p{{color:var(--muted)}}section{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}}
article{{background:rgba(13,27,36,.9);border:1px solid var(--line);border-radius:18px;padding:18px}}
.notice{{border:1px dashed var(--accent);padding:16px;border-radius:14px;margin:20px 0}}
</style></head><body><main><div class='eyebrow'>Offline-first persistent starts</div><h1>Adventure Save Slots</h1>
<div class='notice'>Default: seven-pass local seed forge. Optional: import one external AI proposal before creation. Both slots become fully local, blind, replayable expeditions immediately after creation.</div>
<section>{cards}</section></main></body></html>"""
(OUTPUT / "slot_manager.html").write_text(html, encoding="utf-8")

summary = {
    "schema": "axm.adventure-slot-demo.v1",
    "slots": rows,
    "offline_verification": verify_adventure_slot(SLOTS, "offline-foundation"),
    "external_verification": verify_adventure_slot(SLOTS, "optional-ai-forged"),
    "offline_player_bundle": offline_export.relative_to(ROOT).as_posix(),
    "external_player_bundle": external_export.relative_to(ROOT).as_posix(),
    "external_request": request_path.relative_to(ROOT).as_posix(),
    "external_proposal_example": proposal_path.relative_to(ROOT).as_posix(),
    "slot_manager": (OUTPUT / "slot_manager.html").relative_to(ROOT).as_posix(),
}
(OUTPUT / "demo_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(summary, indent=2, ensure_ascii=False))
