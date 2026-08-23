from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


EXTERIOR_VERSION = "0.14.0-candidate"

EXTERIOR_SYSTEM_CHANNELS: dict[str, tuple[str, tuple[str, ...]]] = {
    "electrical_power_generation": (
        "power_arrays",
        ("array_tracking_sweep", "power_glint_pulse"),
    ),
    "thermal_control": (
        "thermal_rejection",
        ("radiator_shimmer", "heat_rejection_wave"),
    ),
    "main_propulsion": (
        "main_propulsion",
        ("engine_core_breathe", "plume_rehearsal"),
    ),
    "reaction_control": (
        "reaction_control",
        ("attitude_ring", "rcs_puff_rehearsal"),
    ),
    "communications": (
        "communications",
        ("antenna_tracking_sweep", "signal_lane_pulse"),
    ),
    "external_sensors": (
        "external_sensors",
        ("sensor_scan_cone", "target_lock_pulse"),
    ),
    "docking_airlock_eva": (
        "docking_eva",
        ("docking_alignment_tunnel", "eva_tether_rehearsal"),
    ),
    "robotics_and_probe_operations": (
        "robotics_probe",
        ("robot_arm_inspection_sweep", "probe_deployment_rehearsal"),
    ),
}

RESOURCE_CHANNELS = {
    "reactor_reserve_percent": "power_arrays",
    "fuel_percent": "main_propulsion",
    "heat_percent": "thermal_rejection",
    "sensor_health_percent": "external_sensors",
    "hull_integrity_percent": "docking_eva",
    "probe_count": "robotics_probe",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any, domain: str) -> str:
    return hashlib.sha256(f"{domain}|{_canonical(value)}".encode("utf-8")).hexdigest()


def _select_blueprint(registry: dict[str, Any]) -> dict[str, Any]:
    if registry.get("schema") != "axm.ship-system-blueprint-registry.v1":
        raise ValueError("unsupported ship blueprint registry")
    rows = registry.get("blueprints", [])
    wanted = registry.get("default_blueprint_id")
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict) and row.get("id") == wanted:
            return row
    raise ValueError("default ship blueprint not found")


def _system_index(blueprint: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = blueprint.get("systems", [])
    if not isinstance(rows, list):
        raise ValueError("blueprint systems must be a list")
    return {
        str(row["id"]): row
        for row in rows
        if isinstance(row, dict) and row.get("id")
    }


def _module_actors(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = blueprint.get("modules", [])
    if not isinstance(rows, list):
        raise ValueError("blueprint modules must be a list")
    actors: list[dict[str, Any]] = []
    count = max(1, len(rows))
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not row.get("id"):
            continue
        actor = {
            "module_id": str(row["id"]),
            "functions": sorted({str(v) for v in row.get("functions", []) if v}),
            "contains_rooms": sorted({str(v) for v in row.get("contains_rooms", []) if v}),
            "presentation_slot": index,
            "presentation_position": {
                "x": round(-1.0 + (2.0 * index / max(1, count - 1)), 4),
                "y": round((index % 2) * 0.12, 4),
                "z": round((index - (count - 1) / 2.0) * 0.05, 4),
            },
            "geometry_authority": "ordered_module_presentation_layout_not_physical_vehicle_dimensions",
            "may_claim_physical_geometry": False,
        }
        actors.append(actor)
    return actors


def _system_actors(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    systems = _system_index(blueprint)
    actors: list[dict[str, Any]] = []
    for order, system_id in enumerate(EXTERIOR_SYSTEM_CHANNELS):
        system = systems.get(system_id)
        if system is None:
            continue
        role, channels = EXTERIOR_SYSTEM_CHANNELS[system_id]
        actors.append({
            "actor_id": f"exterior-system:{system_id}:v1",
            "system_id": system_id,
            "display_name": system.get("display_name", system_id),
            "category": system.get("category"),
            "criticality": system.get("criticality"),
            "visual_role": role,
            "animation_channels": list(channels),
            "declared_functions": copy.deepcopy(system.get("functions", [])),
            "declared_dependencies": sorted({str(v) for v in system.get("dependencies", []) if v}),
            "room_bindings": sorted({str(v) for v in system.get("room_bindings", []) if v}),
            "presentation_slot": order,
            "operation_state": "UNASSESSED_NO_AUTHORITATIVE_LIVE_SYSTEM_STATE_IN_PRESENTATION_SOURCE",
            "animation_semantics": "CAPABILITY_AND_REHEARSAL_ACTOR_NOT_OPERATION_EXECUTION",
            "may_claim_operation_active": False,
            "may_execute_operation": False,
            "may_claim_physical_hardware_geometry": False,
        })
    return actors


def _procedure_index(procedure_catalog: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if procedure_catalog is None:
        return {}
    if procedure_catalog.get("schema") != "axm.failure-procedure-catalog.v1":
        raise ValueError("unsupported failure procedure catalog")
    rows = procedure_catalog.get("procedures", [])
    if not isinstance(rows, list):
        raise ValueError("procedure catalog procedures must be a list")
    return {
        str(row.get("source_failure_id")): row
        for row in rows
        if isinstance(row, dict) and row.get("source_failure_id")
    }


def _procedure_rehearsal_tracks(
    procedure_catalog: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    procedures = _procedure_index(procedure_catalog)
    rows: list[dict[str, Any]] = []
    for failure_id in sorted(procedures):
        procedure = procedures[failure_id]
        system_id = str(procedure.get("source_system_id") or "")
        if system_id not in EXTERIOR_SYSTEM_CHANNELS:
            continue
        visual_role = EXTERIOR_SYSTEM_CHANNELS[system_id][0]
        rows.append({
            "track_id": f"exterior-rehearsal:{failure_id}:v1",
            "source_failure_id": failure_id,
            "source_system_id": system_id,
            "source_role_id": procedure.get("primary_role_id"),
            "source_station_id": procedure.get("primary_station_id"),
            "visual_role": visual_role,
            "procedure_status": procedure.get("status"),
            "animation_semantics": "FAILURE_PROCEDURE_REHEARSAL_FOCUS_ONLY_NOT_ACTIVE_EXTERNAL_OPERATION",
            "may_claim_fault_active": False,
            "may_execute_response": False,
            "may_execute_operation": False,
        })
    return rows


def _cue_text(cue: dict[str, Any]) -> str:
    values = [
        cue.get("action"),
        cue.get("action_category"),
        cue.get("outcome_id"),
        cue.get("outcome_title"),
    ]
    return " ".join(str(v or "").lower() for v in values)


def _cue_focus(cue: dict[str, Any]) -> str:
    text = _cue_text(cue)
    if any(token in text for token in ("probe", "robot", "payload")):
        return "robotics_probe"
    if any(token in text for token in ("dock", "eva", "airlock", "transfer")):
        return "docking_eva"
    if any(token in text for token in ("maneuver", "trajectory", "orbit", "burn", "propulsion")):
        return "main_propulsion"
    if any(token in text for token in ("attitude", "point", "navigation", "nav")):
        return "reaction_control"
    if any(token in text for token in ("scan", "observe", "sensor", "science", "anomaly")):
        return "external_sensors"
    if any(token in text for token in ("signal", "communicat", "transmit", "telemetry", "downlink", "uplink")):
        return "communications"
    return "communications"


def _cue_choreography(storyboard: dict[str, Any]) -> list[dict[str, Any]]:
    if storyboard.get("schema") != "axm.main-simulator-temporal-storyboard.v1":
        raise ValueError("unsupported temporal storyboard")
    rows: list[dict[str, Any]] = []
    for cue in storyboard.get("cues", []):
        if not isinstance(cue, dict) or not cue.get("cue_id"):
            continue
        rows.append({
            "cue_id": cue.get("cue_id"),
            "source_event_hash": cue.get("source_event_hash"),
            "visual_role": _cue_focus(cue),
            "target_planet_id": cue.get("target_planet_id"),
            "target_planet_name": cue.get("target_planet_name"),
            "classification_authority": "presentation_keyword_routing_only",
            "animation_semantics": "REPLAY_FOCUS_ONLY_DOES_NOT_CLAIM_OPERATION_EXECUTED",
            "may_retarget_event": False,
            "may_execute_operation": False,
        })
    return rows


def _resource_channels(scene: dict[str, Any]) -> list[dict[str, Any]]:
    if scene.get("schema") != "axm.low-graphic-3d-scene.v1":
        raise ValueError("unsupported low-graphic 3D scene")
    resources = scene.get("source_runtime_resource_snapshot", {})
    resources = resources if isinstance(resources, dict) else {}
    rows: list[dict[str, Any]] = []
    for resource_id, visual_role in RESOURCE_CHANNELS.items():
        if resource_id not in resources:
            continue
        rows.append({
            "resource_id": resource_id,
            "source_value": copy.deepcopy(resources[resource_id]),
            "visual_role": visual_role,
            "visual_semantics": "COPIED_SOURCE_VALUE_DISPLAY_ONLY",
            "may_infer_missing_value": False,
            "may_modify_resource": False,
        })
    return rows


def build_exterior_operations_animation(
    blueprint_registry: dict[str, Any],
    scene: dict[str, Any],
    storyboard: dict[str, Any],
    *,
    procedure_catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blueprint = _select_blueprint(blueprint_registry)
    module_actors = _module_actors(blueprint)
    system_actors = _system_actors(blueprint)
    packet = {
        "schema": "axm.exterior-operations-animation.v1",
        "version": EXTERIOR_VERSION,
        "blueprint_id": blueprint.get("id"),
        "blueprint_scope": blueprint.get("scope"),
        "source_scene_hash": scene.get("scene_hash"),
        "module_actors": module_actors,
        "system_actors": system_actors,
        "procedure_rehearsal_tracks": _procedure_rehearsal_tracks(procedure_catalog),
        "cue_choreography": _cue_choreography(storyboard),
        "resource_visual_channels": _resource_channels(scene),
        "presentation_modes": [
            "director",
            "systems",
            "communications",
            "docking",
            "eva",
            "probe",
        ],
        "visual_detail_profiles": {
            "eco": {
                "particle_budget": 8,
                "trail_samples": 4,
                "secondary_actor_motion": False,
            },
            "standard": {
                "particle_budget": 18,
                "trail_samples": 8,
                "secondary_actor_motion": True,
            },
            "rich": {
                "particle_budget": 32,
                "trail_samples": 12,
                "secondary_actor_motion": True,
            },
        },
        "default_visual_detail": "standard",
        "authority": "read_only_exterior_capability_and_rehearsal_presentation",
        "truth_boundary": (
            "Exterior modules, arrays, radiators, antennas, thruster effects, docking tunnels, EVA figures, robotic arms, probes and sensor cones are presentation actors derived from declared modules, systems, source resources and immutable cue/procedure context. They do not establish physical dimensions, live mechanism state, actual thrust, docking, EVA, probe deployment, or operation execution."
        ),
        "renderer_may_animate_exterior_capability_actors": True,
        "renderer_may_adjust_visual_detail": True,
        "renderer_may_claim_physical_vehicle_geometry": False,
        "renderer_may_claim_operation_active": False,
        "renderer_may_execute_operation": False,
        "renderer_may_apply_thrust": False,
        "renderer_may_dock": False,
        "renderer_may_begin_eva": False,
        "renderer_may_deploy_probe": False,
        "renderer_may_move_authoritative_robotics": False,
        "renderer_may_modify_resources": False,
        "renderer_may_retarget_event": False,
    }
    packet["animation_hash"] = _hash(packet, "AXM-EXTERIOR-OPERATIONS-ANIMATION-V1")
    return packet
