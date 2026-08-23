from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .bridge_rehearsal import build_rehearsal_catalog
from .damage_topology import build_damage_topology_catalog
from .failure_procedures import build_failure_procedure_catalog
from .fault_clearance_apply import build_clearance_apply_contract_catalog
from .repair_verification import build_repair_gate_catalog


OPERATIONS_VERSION = "0.8.0-candidate"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any, domain: str) -> str:
    return hashlib.sha256(f"{domain}|{_canonical(value)}".encode("utf-8")).hexdigest()


def build_operations_context(runtime: dict[str, Any]) -> dict[str, Any]:
    """Create a read-only presentation context from authoritative runtime state."""
    resources = copy.deepcopy(runtime.get("resources", {}))
    threads = runtime.get("threads", {}) if isinstance(runtime.get("threads"), dict) else {}
    open_ids = list(runtime.get("open_threads", [])) if isinstance(runtime.get("open_threads"), list) else []
    action_menu = runtime.get("action_menu", {}) if isinstance(runtime.get("action_menu"), dict) else {}
    actions = action_menu.get("actions", []) if isinstance(action_menu.get("actions"), list) else []
    thread_rows = []
    for thread_id in open_ids[:8]:
        raw = threads.get(thread_id, {}) if isinstance(threads.get(thread_id), dict) else {}
        thread_rows.append({"thread_id":thread_id,"title":raw.get("title",thread_id),"kind":raw.get("kind","unknown"),"status":raw.get("status","unknown"),"depth":raw.get("depth"),"visits":raw.get("visits"),"target_planet_id":raw.get("target_planet_id"),"updated_turn":raw.get("updated_turn"),"authority":"read_only_runtime_summary"})
    action_rows = []
    for raw in actions[:6]:
        if isinstance(raw, dict):
            action_rows.append({"action_id":raw.get("action_id"),"label":raw.get("label"),"category":raw.get("category"),"source_thread":raw.get("source_thread"),"target_planet_id":raw.get("target_planet_id"),"intent":raw.get("intent"),"priority":raw.get("priority"),"authority":"inspect_only_not_executable","may_execute":False})
    packet = {"schema":"axm.living-operations-context.v1","version":OPERATIONS_VERSION,"source_runtime_schema":runtime.get("schema"),"source_turn":runtime.get("turn"),"source_mission_time_hours":runtime.get("mission_time_hours"),"resources":resources,"open_thread_count":len(open_ids),"open_threads":thread_rows,"action_menu_version":action_menu.get("menu_version"),"available_action_count":len(actions),"actions":action_rows,"authority":"read_only_presentation_summary","may_execute_action":False,"may_modify_runtime":False,"may_close_thread":False,"may_change_truth_labels":False}
    packet["context_hash"] = _hash(packet, "AXM-LIVING-OPERATIONS-CONTEXT-V1")
    return packet


def enrich_storyboard(
    storyboard: dict[str, Any],
    runtime: dict[str, Any],
    failure_registry: dict[str, Any] | None = None,
    station_registry: dict[str, Any] | None = None,
    blueprint_registry: dict[str, Any] | None = None,
    interface_graph: dict[str, Any] | None = None,
    interior_registry: dict[str, Any] | None = None,
    room_interaction_registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if storyboard.get("schema") != "axm.main-simulator-temporal-storyboard.v1":
        raise ValueError("unsupported storyboard schema")
    if runtime.get("schema") != "axm.adventure-runtime.v4":
        raise ValueError("unsupported runtime schema")
    if runtime.get("system_id") != storyboard.get("system_id"):
        raise ValueError("runtime/storyboard system mismatch")
    if runtime.get("mission_time_hours") != storyboard.get("mission_time_hours"):
        raise ValueError("runtime/storyboard mission time mismatch")
    if (failure_registry is None) != (station_registry is None):
        raise ValueError("failure and station registries must be supplied together")

    topology_inputs = (
        blueprint_registry,
        interface_graph,
        interior_registry,
        room_interaction_registry,
    )
    if any(value is not None for value in topology_inputs) and not all(value is not None for value in topology_inputs):
        raise ValueError("blueprint, interface, interior, and room-interaction registries must be supplied together")
    if all(value is not None for value in topology_inputs) and failure_registry is None:
        raise ValueError("damage topology requires the failure registry")

    out = copy.deepcopy(storyboard)
    operations_context = build_operations_context(runtime)
    out["operations_context"] = operations_context
    out["bridge_rehearsal"] = build_rehearsal_catalog(operations_context)

    if failure_registry is not None and station_registry is not None:
        out["failure_procedures"] = build_failure_procedure_catalog(failure_registry, station_registry)

    if all(value is not None for value in topology_inputs):
        out["damage_topology"] = build_damage_topology_catalog(
            failure_registry,
            blueprint_registry,
            interface_graph,
            interior_registry,
            room_interaction_registry,
            procedure_catalog=out.get("failure_procedures"),
        )
        out["repair_verification"] = build_repair_gate_catalog(
            out["failure_procedures"],
            out["damage_topology"],
        )
        out["fault_clearance_apply"] = build_clearance_apply_contract_catalog(
            out["repair_verification"],
            out["failure_procedures"],
        )

    out["living_operations"] = {
        "schema":"axm.living-operations-presentation-profile.v1",
        "version":OPERATIONS_VERSION,
        "director_mode":"receipt_phase_driven_camera_choreography",
        "crew_mode":"receipt_phase_driven_reenactment_only",
        "resource_mode":"read_only_source_snapshot",
        "thread_mode":"read_only_runtime_summary",
        "action_mode":"inspect_and_rehearse_only_not_executable",
        "rehearsal_mode":"deterministic_planning_rehearsal_with_hold_points",
        "failure_procedure_mode":"versioned_evidence_gated_review_only" if failure_registry is not None else "not_loaded",
        "damage_topology_mode":"derived_existing_graph_composition_only" if "damage_topology" in out else "not_loaded",
        "repair_verification_mode":"external_execution_receipts_plus_post_repair_evidence_gate" if "repair_verification" in out else "not_loaded",
        "fault_clearance_apply_mode":"authoritative_ship_state_engine_available_requires_verified_candidate_authorization_and_exact_reconciliation" if "fault_clearance_apply" in out else "not_loaded",
        "authoritative_clearance_engine_present": "fault_clearance_apply" in out,
        "renderer_may_apply_fault_clearance": False,
        "may_advance_mission_time":False,
        "may_append_event":False,
        "may_retarget_event":False,
        "may_modify_runtime_resources":False,
        "may_execute_action":False,
        "may_execute_failure_response":False,
        "may_execute_repair":False,
        "may_record_external_execution_as_fact_without_receipt":False,
        "may_consume_spares":False,
        "may_fabricate_repair_part":False,
        "may_clear_fault":False,
        "may_claim_neighbor_failed":False,
        "may_close_thread":False,
        "may_change_truth_labels":False,
    }
    out["living_operations"]["profile_hash"] = _hash(out["living_operations"], "AXM-LIVING-OPERATIONS-PRESENTATION-PROFILE-V1")
    return out
