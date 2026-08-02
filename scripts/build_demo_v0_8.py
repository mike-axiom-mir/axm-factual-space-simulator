from __future__ import annotations

import json
import shutil
from pathlib import Path

from axm_star_sim.blind_forge import (
    forge_blind_scenario,
    resolve_session_action,
    reveal_session,
    write_blind_forge_session,
)
from axm_star_sim.generator import generate_system

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "blind_ai_forge_demo"
SAMPLE = ROOT / "output" / "blind_ai_forge_sample_run"


def build(path: Path, run_sample: bool) -> dict:
    if path.exists():
        shutil.rmtree(path)
    system = generate_system("MIKE-AXIOM-MIR-BLIND-UNIVERSE-0001").to_dict()
    private_payload, public_bundle = forge_blind_scenario(
        system,
        "AXIOM-MIR-PREPLAY-REASONING-SEED-0001",
        forge_author="Axiom/Mir pre-play possibility synthesis",
    )
    paths = write_blind_forge_session(path, system, private_payload, public_bundle)
    actions = []
    if run_sample:
        sequence = [
            "broad_spectrum_survey",
            "repeat_changed_geometry",
            "switch_instrument_family",
            "measure_chemical_complexity",
            "abiotic_control_campaign",
            "independent_blind_reanalysis",
        ]
        for index, action in enumerate(sequence, 1):
            result = resolve_session_action(path, action, f"DEMO-ENTROPY-{index:02d}")
            actions.append({
                "turn": result["event"]["turn"],
                "action": action,
                "outcome": result["event"]["observation"]["outcome_class"],
                "stage": result["event"]["evidence_stage_after"],
            })
        verification = reveal_session(path)
    else:
        verification = None
    summary = {
        "schema": "axm.blind-forge-demo.v1",
        "system_id": system["system_id"],
        "system_name": system["name"],
        "commitment": paths["commitment"],
        "player_public": (path / "player_public").relative_to(ROOT).as_posix(),
        "forge_private": (path / "forge_private").relative_to(ROOT).as_posix(),
        "sample_actions": actions,
        "reveal_verification": verification,
        "handoff_rule": "Give only player_public to the exploring AI or human.",
    }
    (path / "demo_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


if __name__ == "__main__":
    initial = build(OUTPUT, run_sample=False)
    sample = build(SAMPLE, run_sample=True)
    print(json.dumps({"initial": initial, "sample": sample}, indent=2, ensure_ascii=False))
