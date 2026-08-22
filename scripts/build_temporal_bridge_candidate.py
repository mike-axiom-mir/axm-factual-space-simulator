from __future__ import annotations

import json
from pathlib import Path

from axm_star_sim.temporal_bridge_view import render_temporal_bridge
from axm_star_sim.temporal_renderer_adapter import (
    build_renderer_authorization,
    build_temporal_storyboard,
    load_verified_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "output" / "persistent_atlas_demo" / "expedition_alpha"
OUTPUT = ROOT / "output" / "temporal_bridge_candidate" / "temporal_bridge.html"


def main() -> int:
    snapshot = load_verified_snapshot(
        system_bytes=(SOURCE / "system.json").read_bytes(),
        runtime_bytes=(SOURCE / "runtime_state.json").read_bytes(),
        event_ledger_bytes=(SOURCE / "event_ledger.jsonl").read_bytes(),
        manifest_bytes=(SOURCE / "manifest.json").read_bytes(),
        source_repository="mike-axiom-mir/axm-factual-space-simulator",
        source_commit="f7939f24faf970e32d65b561ec5b2f8eb1e41d70",
    )
    board = build_temporal_storyboard(snapshot)
    authorization = build_renderer_authorization(snapshot["import_receipt"])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render_temporal_bridge(board, snapshot["import_receipt"]), encoding="utf-8")
    print(json.dumps({
        "schema": "axm.temporal-bridge-candidate-build.v2",
        "version": board["version"],
        "system_id": board["system_id"],
        "events": len(board["cues"]),
        "source_mission_time_hours": board["mission_time_hours"],
        "temporal_reconstruction_status": board["temporal_reconstruction"]["status"],
        "state_change_receipt_statuses": [
            cue["state_change_receipt"]["status"] for cue in board["cues"]
        ],
        "camera_presets": [row["id"] for row in board["presentation_profiles"]["camera_presets"]],
        "replay_scrubber": board["presentation_profiles"]["replay_scrubber"],
        "object_inspector": board["presentation_profiles"]["object_inspector"],
        "output": str(OUTPUT.relative_to(ROOT)),
        "authority": "presentation_renderer_only",
        "renderer_authorization_receipt": authorization["authorization_receipt"],
        "reconstruction_receipt": authorization["reconstruction_packet"]["reconstruction_receipt"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
