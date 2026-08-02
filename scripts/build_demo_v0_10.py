from __future__ import annotations
import json
from pathlib import Path
from axm_star_sim.bridge_visual_core import (
    first_bridge_reference_layout,
    make_reconstruction_packet,
    resolve_start_package,
    pin_start_package_for_save,
    validate_layout_packet,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "bridge_visual_core_demo"
OUT.mkdir(parents=True, exist_ok=True)
package = resolve_start_package()
pin = pin_start_package_for_save(package)
layout = first_bridge_reference_layout()
validation = validate_layout_packet(layout, pin)
reconstruction = make_reconstruction_packet(
    pin,
    historical_state_hash="f" * 64,
    target_render_profile_id="axm.render.holodeck-reconstruction.v1",
)
report = {
    "schema": "axm.bridge-visual-core-demo.v1",
    "start_package": package,
    "start_pin": pin,
    "layout_validation": validation,
    "future_reconstruction_packet": reconstruction,
    "first_bridge_is_one_of_many": package["bridge_archetype"]["scope"],
}
(OUT / "demo_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({
    "valid": validation["valid"],
    "bridge": package["bridge_archetype"]["id"],
    "timeline": package["timeline_start"]["id"],
    "crew": package["crew_start"]["id"],
    "future_renderer": reconstruction["target_render_profile_id"],
}, indent=2))

# Restore the canonical visual proof after deterministic data rebuild.
_template = ROOT / "assets" / "demo_templates" / "paint_foundation_bridge.html"
(OUT / "paint_foundation_bridge.html").write_text(_template.read_text(encoding="utf-8"), encoding="utf-8")
