from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .bridge_rehearsal import build_rehearsal_catalog
from .causal_cinematic_director import build_causal_cinematic_director
from .damage_topology import build_damage_topology_catalog
from .exterior_operations_animation import build_exterior_operations_animation
from .failure_procedures import build_failure_procedure_catalog
from .fault_clearance_apply import build_clearance_apply_contract_catalog
from .interactive_exploration import build_interactive_exploration
from .living_interior_animation import build_living_interior_animation
from .low_graphic_scene import build_low_graphic_3d_scene
from .operational_readiness import build_operational_readiness_contract_catalog
from .post_clearance_recovery import build_post_clearance_recovery_contract_catalog
from .repair_verification import build_repair_gate_catalog


OPERATIONS_VERSION = "0.15.0-candidate"


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

    topology_inputs = (blueprint_registry, interface_graph, interior_registry, room_interaction_registry)
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
        out["damage_topology"] = build_damage_topology_catalog(failure_registry, blueprint_registry, interface_graph, interior_registry, room_interaction_registry, procedure_catalog=out.get("failure_procedures"))
        out["repair_verification"] = build_repair_gate_catalog(out["failure_procedures"], out["damage_topology"])
        out["fault_clearance_apply"] = build_clearance_apply_contract_catalog(out["repair_verification"], out["failure_procedures"])
        out["post_clearance_recovery"] = build_post_clearance_recovery_contract_catalog(out["fault_clearance_apply"])
        out["operational_readiness"] = build_operational_readiness_contract_catalog(out["post_clearance_recovery"])
        out["low_graphic_3d_scene"] = build_low_graphic_3d_scene(operations_context, station_registry, interior_registry, damage_topology_catalog=out["damage_topology"])
        out["living_interior_animation"] = build_living_interior_animation(out["low_graphic_3d_scene"], procedure_catalog=out.get("failure_procedures"))
        out["exterior_operations_animation"] = build_exterior_operations_animation(blueprint_registry, out["low_graphic_3d_scene"], out, procedure_catalog=out.get("failure_procedures"))
        out["causal_cinematic_director"] = build_causal_cinematic_director(out, out["exterior_operations_animation"], out["living_interior_animation"])
        out["interactive_exploration"] = build_interactive_exploration(
            out["low_graphic_3d_scene"],
            out["living_interior_animation"],
            out["exterior_operations_animation"],
            out["causal_cinematic_director"],
        )

    out["living_operations"] = {
        "schema":"axm.living-operations-presentation-profile.v1",
        "version":OPERATIONS_VERSION,
        "director_mode":"immutable_cue_segment_cinematic_choreography",
        "crew_mode":"receipt_phase_driven_reenactment_only",
        "resource_mode":"read_only_source_snapshot",
        "thread_mode":"read_only_runtime_summary",
        "action_mode":"inspect_and_rehearse_only_not_executable",
        "rehearsal_mode":"deterministic_planning_rehearsal_with_hold_points",
        "failure_procedure_mode":"versioned_evidence_gated_review_only" if failure_registry is not None else "not_loaded",
        "damage_topology_mode":"derived_existing_graph_composition_only" if "damage_topology" in out else "not_loaded",
        "repair_verification_mode":"external_execution_receipts_plus_post_repair_evidence_gate" if "repair_verification" in out else "not_loaded",
        "fault_clearance_apply_mode":"authoritative_ship_state_engine_available_requires_verified_candidate_authorization_and_exact_reconciliation" if "fault_clearance_apply" in out else "not_loaded",
        "post_clearance_recovery_mode":"residual_state_assessment_plus_explicit_commander_safe_state_exit_authorization" if "post_clearance_recovery" in out else "not_loaded",
        "operational_readiness_mode":"truthful_residual_aware_operating_mode_classification_plus_read_only_capability_envelope" if "operational_readiness" in out else "not_loaded",
        "low_graphic_3d_mode":"whole_simulator_2_5d_read_only_scene_projection" if "low_graphic_3d_scene" in out else "not_loaded",
        "living_interior_animation_mode":"registered_room_graph_portals_abstract_machinery_ambience_and_rehearsal_traversal" if "living_interior_animation" in out else "not_loaded",
        "exterior_operations_animation_mode":"declared_module_and_system_capability_actors_plus_rehearsal_only_external_choreography" if "exterior_operations_animation" in out else "not_loaded",
        "causal_cinematic_director_mode":"immutable_cue_segment_order_plus_recorded_state_change_camera_focus" if "causal_cinematic_director" in out else "not_loaded",
        "interactive_exploration_mode":"select_follow_and_inspect_registered_presentation_targets_only" if "interactive_exploration" in out else "not_loaded",
        "authoritative_clearance_engine_present": "fault_clearance_apply" in out,
        "authoritative_recovery_engine_present": "post_clearance_recovery" in out,
        "authoritative_operational_release_engine_present": "operational_readiness" in out,
        "low_graphic_3d_scene_present": "low_graphic_3d_scene" in out,
        "living_interior_animation_present": "living_interior_animation" in out,
        "exterior_operations_animation_present": "exterior_operations_animation" in out,
        "causal_cinematic_director_present": "causal_cinematic_director" in out,
        "interactive_exploration_present": "interactive_exploration" in out,
        "renderer_may_animate": True,
        "renderer_may_animate_room_ambience": "living_interior_animation" in out,
        "renderer_may_animate_portals": "living_interior_animation" in out,
        "renderer_may_animate_crew_reenactment": "living_interior_animation" in out,
        "renderer_may_animate_abstract_machinery": "living_interior_animation" in out,
        "renderer_may_animate_exterior_capability_actors": "exterior_operations_animation" in out,
        "renderer_may_route_camera_from_immutable_cues": "causal_cinematic_director" in out,
        "renderer_may_adjust_visual_detail": "causal_cinematic_director" in out,
        "renderer_may_select_presentation_target": "interactive_exploration" in out,
        "renderer_may_inspect_declared_source_metadata": "interactive_exploration" in out,
        "renderer_may_follow_existing_presentation_context": "interactive_exploration" in out,
        "renderer_may_apply_fault_clearance": False,
        "renderer_may_apply_safe_state_exit": False,
        "renderer_may_apply_operational_release": False,
        "renderer_may_classify_operating_mode": False,
        "renderer_may_execute_operation": False,
        "renderer_may_execute_exterior_operation": False,
        "renderer_may_apply_thrust": False,
        "renderer_may_dock": False,
        "renderer_may_begin_eva": False,
        "renderer_may_deploy_probe": False,
        "renderer_may_reorder_events": False,
        "renderer_may_change_cue_timing_fractions": False,
        "renderer_may_change_authoritative_selection": False,
        "renderer_may_claim_nominal_with_residuals": False,
        "renderer_may_restore_resources": False,
        "renderer_may_remove_load_sheds": False,
        "renderer_may_move_authoritative_crew": False,
        "renderer_may_move_authoritative_robotics": False,
        "renderer_may_open_authoritative_doors": False,
        "renderer_may_claim_physical_hardware": False,
        "renderer_may_claim_physical_vehicle_geometry": False,
        "renderer_may_claim_fault_active_from_rehearsal": False,
        "renderer_may_claim_physical_scene_geometry": False,
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
        "may_exit_safe_state":False,
        "may_claim_neighbor_failed":False,
        "may_close_thread":False,
        "may_change_truth_labels":False,
    }
    out["living_operations"]["profile_hash"] = _hash(out["living_operations"], "AXM-LIVING-OPERATIONS-PRESENTATION-PROFILE-V1")
    return out
