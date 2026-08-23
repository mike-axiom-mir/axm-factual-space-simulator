from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .bridge_rehearsal import build_rehearsal_catalog


OPERATIONS_VERSION = "0.4.0-candidate"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any, domain: str) -> str:
    return hashlib.sha256(f"{domain}|{_canonical(value)}".encode("utf-8")).hexdigest()


def build_operations_context(runtime: dict[str, Any]) -> dict[str, Any]:
    """Create a read-only presentation context from authoritative runtime state.

    The result is intentionally lossy: enough for a bridge presentation, never
    enough to become a second runtime authority. No action is executable here.
    """
    resources = copy.deepcopy(runtime.get("resources", {}))
    threads = runtime.get("threads", {}) if isinstance(runtime.get("threads"), dict) else {}
    open_ids = list(runtime.get("open_threads", [])) if isinstance(runtime.get("open_threads"), list) else []
    action_menu = runtime.get("action_menu", {}) if isinstance(runtime.get("action_menu"), dict) else {}
    actions = action_menu.get("actions", []) if isinstance(action_menu.get("actions"), list) else []

    thread_rows: list[dict[str, Any]] = []
    for thread_id in open_ids[:8]:
        raw = threads.get(thread_id, {}) if isinstance(threads.get(thread_id), dict) else {}
        thread_rows.append({"thread_id":thread_id,"title":raw.get("title",thread_id),"kind":raw.get("kind","unknown"),"status":raw.get("status","unknown"),"depth":raw.get("depth"),"visits":raw.get("visits"),"target_planet_id":raw.get("target_planet_id"),"updated_turn":raw.get("updated_turn"),"authority":"read_only_runtime_summary"})

    action_rows: list[dict[str, Any]] = []
    for raw in actions[:6]:
        if not isinstance(raw, dict):
            continue
        action_rows.append({"action_id":raw.get("action_id"),"label":raw.get("label"),"category":raw.get("category"),"source_thread":raw.get("source_thread"),"target_planet_id":raw.get("target_planet_id"),"intent":raw.get("intent"),"priority":raw.get("priority"),"authority":"inspect_only_not_executable","may_execute":False})

    packet = {"schema":"axm.living-operations-context.v1","version":OPERATIONS_VERSION,"source_runtime_schema":runtime.get("schema"),"source_turn":runtime.get("turn"),"source_mission_time_hours":runtime.get("mission_time_hours"),"resources":resources,"open_thread_count":len(open_ids),"open_threads":thread_rows,"action_menu_version":action_menu.get("menu_version"),"available_action_count":len(actions),"actions":action_rows,"authority":"read_only_presentation_summary","may_execute_action":False,"may_modify_runtime":False,"may_close_thread":False,"may_change_truth_labels":False}
    packet["context_hash"] = _hash(packet, "AXM-LIVING-OPERATIONS-CONTEXT-V1")
    return packet


def enrich_storyboard(storyboard: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    if storyboard.get("schema") != "axm.main-simulator-temporal-storyboard.v1":
        raise ValueError("unsupported storyboard schema")
    if runtime.get("schema") != "axm.adventure-runtime.v4":
        raise ValueError("unsupported runtime schema")
    if runtime.get("system_id") != storyboard.get("system_id"):
        raise ValueError("runtime/storyboard system mismatch")
    source_time = runtime.get("mission_time_hours")
    board_time = storyboard.get("mission_time_hours")
    if source_time != board_time:
        raise ValueError("runtime/storyboard mission time mismatch")

    out = copy.deepcopy(storyboard)
    operations_context = build_operations_context(runtime)
    out["operations_context"] = operations_context
    out["bridge_rehearsal"] = build_rehearsal_catalog(operations_context)
    out["living_operations"] = {"schema":"axm.living-operations-presentation-profile.v1","version":OPERATIONS_VERSION,"director_mode":"receipt_phase_driven_camera_choreography","crew_mode":"receipt_phase_driven_reenactment_only","resource_mode":"read_only_source_snapshot","thread_mode":"read_only_runtime_summary","action_mode":"inspect_and_rehearse_only_not_executable","rehearsal_mode":"deterministic_planning_rehearsal_with_hold_points","may_advance_mission_time":False,"may_append_event":False,"may_retarget_event":False,"may_modify_runtime_resources":False,"may_execute_action":False,"may_close_thread":False,"may_change_truth_labels":False}
    out["living_operations"]["profile_hash"] = _hash(out["living_operations"], "AXM-LIVING-OPERATIONS-PRESENTATION-PROFILE-V1")
    return out
