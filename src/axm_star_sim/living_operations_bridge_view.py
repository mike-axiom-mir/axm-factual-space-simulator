from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

RENDERER_VERSION = "0.10.0-candidate"
ROOT = Path(__file__).resolve().parents[2]
ASSET_DIR = ROOT / "assets" / "demo_templates" / "living_operations_bridge"


def _asset(name: str) -> str:
    return (ASSET_DIR / name).read_text(encoding="utf-8")


def render_living_bridge(storyboard: dict[str, Any], import_receipt: dict[str, Any]) -> str:
    if storyboard.get("schema") != "axm.main-simulator-temporal-storyboard.v1":
        raise ValueError("unsupported storyboard schema")
    if import_receipt.get("status") != "IMPORT_VALID":
        raise ValueError("living renderer requires IMPORT_VALID read-only source receipt")
    if not storyboard.get("cues"):
        raise ValueError("renderer requires at least one immutable event cue")
    if storyboard.get("bridge_rehearsal", {}).get("may_execute_action") is not False:
        raise ValueError("bridge rehearsal must remain non-executable")
    procedures = storyboard.get("failure_procedures")
    if procedures is not None:
        if procedures.get("may_execute_response") is not False:
            raise ValueError("failure procedure catalog must remain non-executable")
        if procedures.get("may_clear_fault") is not False:
            raise ValueError("failure procedure catalog must not clear faults")
    topology = storyboard.get("damage_topology")
    if topology is not None:
        if topology.get("may_execute_repair") is not False:
            raise ValueError("damage topology must remain non-executable")
        if topology.get("may_consume_spares") is not False:
            raise ValueError("damage topology must not consume spares")
        if topology.get("may_clear_fault") is not False:
            raise ValueError("damage topology must not clear faults")
    repair = storyboard.get("repair_verification")
    if repair is not None:
        if repair.get("may_execute_repair") is not False:
            raise ValueError("repair verification gate must not execute repairs")
        if repair.get("may_clear_fault") is not False:
            raise ValueError("repair verification gate must not clear faults")
        if repair.get("fault_cleared") is not False:
            raise ValueError("renderer cannot load a pre-cleared repair gate catalog")
    clearance = storyboard.get("fault_clearance_apply")
    if clearance is not None:
        if clearance.get("fault_cleared") is not False:
            raise ValueError("clearance apply presentation catalog must remain unapplied")
        if clearance.get("may_modify_presentation_runtime") is not False:
            raise ValueError("clearance apply contract must not grant renderer mutation authority")
    recovery = storyboard.get("post_clearance_recovery")
    if recovery is not None:
        if recovery.get("safe_state_exited") is not False:
            raise ValueError("recovery presentation catalog must remain unapplied")
        if recovery.get("may_modify_presentation_runtime") is not False:
            raise ValueError("recovery contract must not grant renderer mutation authority")
        if recovery.get("may_restore_resources") is not False:
            raise ValueError("recovery presentation contract must not restore resources")

    template = _asset("shell.html")
    css = (
        _asset("living_operations_bridge.css")
        + "\n" + _asset("bridge_rehearsal_v0_4.css")
        + "\n" + _asset("failure_procedure_v0_5.css")
        + "\n" + _asset("damage_topology_v0_6.css")
        + "\n" + _asset("repair_verification_v0_7.css")
        + "\n" + _asset("fault_clearance_apply_v0_8.css")
        + "\n" + _asset("post_clearance_recovery_v0_10.css")
    )
    js = (
        _asset("living_operations_bridge_js_part1.txt")
        + _asset("living_operations_bridge_js_part2.txt")
        + "\n" + _asset("bridge_rehearsal_v0_4.js")
        + "\n" + _asset("failure_procedure_v0_5.js")
        + "\n" + _asset("damage_topology_v0_6.js")
        + "\n" + _asset("repair_verification_v0_7.js")
        + "\n" + _asset("fault_clearance_apply_v0_8.js")
        + "\n" + _asset("post_clearance_recovery_v0_10.js")
    )
    payload = json.dumps(storyboard, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    receipt = json.dumps(import_receipt, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    title = html.escape(str(storyboard.get("system_name", "AXM Factual Space Simulator")))
    return template.replace("__AXM_TITLE__", title).replace("__AXM_STORYBOARD__", payload).replace("__AXM_RECEIPT__", receipt).replace("__AXM_CSS__", css).replace("__AXM_JS__", js)
