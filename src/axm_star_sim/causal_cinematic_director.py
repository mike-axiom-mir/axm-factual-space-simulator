from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


DIRECTOR_VERSION = "0.14.0-candidate"

RESOURCE_ROOM_FOCUS = {
    "reactor_reserve_percent": "engineering",
    "fuel_percent": "engineering",
    "heat_percent": "engineering",
    "sensor_health_percent": "research_strategy",
    "probe_count": "research_strategy",
    "knowledge_points": "research_strategy",
    "hull_integrity_percent": "central_corridor",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any, domain: str) -> str:
    return hashlib.sha256(f"{domain}|{_canonical(value)}".encode("utf-8")).hexdigest()


def _validate_sources(
    storyboard: dict[str, Any],
    exterior: dict[str, Any],
    interior: dict[str, Any],
) -> None:
    if storyboard.get("schema") != "axm.main-simulator-temporal-storyboard.v1":
        raise ValueError("unsupported temporal storyboard")
    if exterior.get("schema") != "axm.exterior-operations-animation.v1":
        raise ValueError("unsupported exterior animation contract")
    if interior.get("schema") != "axm.living-interior-animation.v1":
        raise ValueError("unsupported living interior animation contract")


def _exterior_cue_index(exterior: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("cue_id")): row
        for row in exterior.get("cue_choreography", [])
        if isinstance(row, dict) and row.get("cue_id")
    }


def _telemetry_focus_room(cue: dict[str, Any]) -> str:
    changes = cue.get("state_change_receipt", {}).get("changes", [])
    if isinstance(changes, list):
        for row in changes:
            if not isinstance(row, dict):
                continue
            room = RESOURCE_ROOM_FOCUS.get(str(row.get("resource_id") or ""))
            if room is not None and row.get("direction") != "no_change":
                return room
    category = str(cue.get("action_category") or "").lower()
    if "science" in category or "research" in category:
        return "research_strategy"
    return "command_deck"


def _segment_fraction(cue: dict[str, Any], segment_id: str) -> float:
    for row in cue.get("playback_segments", []):
        if isinstance(row, dict) and row.get("id") == segment_id:
            try:
                value = float(row.get("display_fraction"))
            except (TypeError, ValueError):
                break
            if value > 0:
                return value
    raise ValueError(f"cue is missing valid playback segment: {segment_id}")


def _shot_plan(
    cue: dict[str, Any],
    exterior_cue: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    exterior_role = (exterior_cue or {}).get("visual_role", "communications")
    focus_room = _telemetry_focus_room(cue)
    rows = [
        {
            "shot_id": f"{cue.get('cue_id')}:command",
            "source_segment_id": "command_outbound",
            "display_fraction": _segment_fraction(cue, "command_outbound"),
            "scene_mode": "legacy_bridge",
            "interior_life_mode": "ambient",
            "focus_room_id": "command_deck",
            "exterior_visual_role": exterior_role,
            "camera_semantics": "COMMAND_CONTEXT_FROM_EXISTING_CUE",
        },
        {
            "shot_id": f"{cue.get('cue_id')}:observation",
            "source_segment_id": "observation_window",
            "display_fraction": _segment_fraction(cue, "observation_window"),
            "scene_mode": "exterior_orbit",
            "interior_life_mode": "ambient",
            "focus_room_id": None,
            "exterior_visual_role": exterior_role,
            "camera_semantics": "TARGET_AND_EXTERNAL_CONTEXT_FROM_EXISTING_CUE",
        },
        {
            "shot_id": f"{cue.get('cue_id')}:telemetry",
            "source_segment_id": "telemetry_return",
            "display_fraction": _segment_fraction(cue, "telemetry_return"),
            "scene_mode": "interior_follow",
            "interior_life_mode": "systems",
            "focus_room_id": focus_room,
            "exterior_visual_role": exterior_role,
            "camera_semantics": "RECORDED_STATE_CHANGE_FOCUS_WITHOUT_VALUE_JUDGMENT",
        },
    ]
    source_total = sum(
        float(row.get("display_fraction", 0.0))
        for row in cue.get("playback_segments", [])
        if isinstance(row, dict)
    )
    shot_total = sum(row["display_fraction"] for row in rows)
    if abs(source_total - shot_total) > 1e-9:
        raise ValueError("cinematic shot fractions do not preserve source playback fractions")
    for row in rows:
        row["authority"] = "presentation_camera_routing_only"
        row["may_reorder_event"] = False
        row["may_modify_cue"] = False
        row["may_execute_operation"] = False
    return rows


def build_causal_cinematic_director(
    storyboard: dict[str, Any],
    exterior: dict[str, Any],
    interior: dict[str, Any],
) -> dict[str, Any]:
    _validate_sources(storyboard, exterior, interior)
    exterior_by_cue = _exterior_cue_index(exterior)
    cue_plans: list[dict[str, Any]] = []
    for index, cue in enumerate(storyboard.get("cues", [])):
        if not isinstance(cue, dict) or not cue.get("cue_id"):
            continue
        cue_id = str(cue["cue_id"])
        plan = {
            "cue_id": cue_id,
            "source_display_index": cue.get("display_index", index),
            "source_turn": cue.get("turn"),
            "source_event_hash": cue.get("source_event_hash"),
            "shots": _shot_plan(cue, exterior_by_cue.get(cue_id)),
            "shot_order_authority": "exact_source_segment_order",
            "time_mapping": cue.get("time_mapping"),
            "may_reorder_event": False,
            "may_modify_event": False,
        }
        plan["plan_hash"] = _hash(plan, "AXM-CAUSAL-CINEMATIC-CUE-PLAN-V1")
        cue_plans.append(plan)

    packet = {
        "schema": "axm.causal-cinematic-director.v1",
        "version": DIRECTOR_VERSION,
        "source_storyboard_hash": storyboard.get("storyboard_hash"),
        "source_exterior_animation_hash": exterior.get("animation_hash"),
        "source_interior_animation_hash": interior.get("animation_hash"),
        "cue_plan_count": len(cue_plans),
        "cue_plans": cue_plans,
        "default_enabled": True,
        "transition_profile": {
            "cut": "segment_boundary_or_manual_cue_change",
            "camera_drift": "bounded_subtle_presentation_motion",
            "focus_transition": "brief_crossfade_or_pan_when_motion_allowed",
            "reduced_motion": "hard_cut_no_drift",
        },
        "visual_detail_profiles": copy.deepcopy(exterior.get("visual_detail_profiles", {})),
        "default_visual_detail": exterior.get("default_visual_detail", "standard"),
        "authority": "read_only_causal_camera_direction",
        "truth_boundary": (
            "The director may choose presentation shots and visual detail from immutable cue order, recorded state-change receipts and declared exterior/interior animation contracts. It cannot change event order, mission time, targets, outcomes, truth labels, resource values, or operation state."
        ),
        "renderer_may_route_camera_from_immutable_cues": True,
        "renderer_may_adjust_visual_detail": True,
        "renderer_may_reorder_events": False,
        "renderer_may_change_cue_timing_fractions": False,
        "renderer_may_retarget_event": False,
        "renderer_may_modify_world_state": False,
        "renderer_may_execute_operation": False,
        "renderer_may_change_truth_labels": False,
    }
    packet["director_hash"] = _hash(packet, "AXM-CAUSAL-CINEMATIC-DIRECTOR-V1")
    return packet
