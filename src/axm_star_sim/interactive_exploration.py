from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


EXPLORATION_VERSION = "0.15.0-candidate"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any, domain: str) -> str:
    return hashlib.sha256(f"{domain}|{_canonical(value)}".encode("utf-8")).hexdigest()


def _validate_sources(
    scene: dict[str, Any],
    interior: dict[str, Any],
    exterior: dict[str, Any],
    cinematic: dict[str, Any],
) -> None:
    if scene.get("schema") != "axm.low-graphic-3d-scene.v1":
        raise ValueError("unsupported low-graphic 3D scene")
    if interior.get("schema") != "axm.living-interior-animation.v1":
        raise ValueError("unsupported living interior animation contract")
    if exterior.get("schema") != "axm.exterior-operations-animation.v1":
        raise ValueError("unsupported exterior operations animation contract")
    if cinematic.get("schema") != "axm.causal-cinematic-director.v1":
        raise ValueError("unsupported causal cinematic director")


def _target(row: dict[str, Any]) -> dict[str, Any]:
    packet = {
        **row,
        "authority": "presentation_selection_and_inspection_only",
        "may_modify_world_state": False,
        "may_execute_action": False,
        "may_execute_operation": False,
        "may_move_authoritative_crew": False,
        "may_move_authoritative_robotics": False,
        "may_retarget_event": False,
        "may_change_truth_labels": False,
    }
    packet["target_hash"] = _hash(packet, "AXM-INTERACTIVE-EXPLORATION-TARGET-V1")
    return packet


def _room_targets(scene: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for room in scene.get("rooms", []):
        if not isinstance(room, dict) or not room.get("room_id"):
            continue
        room_id = str(room["room_id"])
        rows.append(_target({
            "target_id": f"room:{room_id}",
            "kind": "room",
            "label": str(room.get("display_name") or room_id),
            "selection_status": "AVAILABLE_FOR_PRESENTATION_FOCUS",
            "scene_mode": "interior_follow",
            "focus_room_id": room_id,
            "exterior_visual_role": None,
            "source_ids": [room_id],
            "inspection": {
                "room_type": room.get("room_type"),
                "adjacent_room_ids": copy.deepcopy(room.get("adjacent_rooms", [])),
                "system_binding_ids": copy.deepcopy(room.get("ship_system_bindings", [])),
                "purpose": copy.deepcopy(room.get("purpose", [])),
                "geometry_authority": room.get("position_authority"),
            },
            "truth_boundary": "Room focus selects registered presentation metadata and a camera target only; it does not move crew or establish physical geometry.",
        }))
    return rows


def _station_targets(scene: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for station in scene.get("station_anchors", []):
        if not isinstance(station, dict) or not station.get("station_id"):
            continue
        station_id = str(station["station_id"])
        room_id = str(station.get("room_id") or "")
        rows.append(_target({
            "target_id": f"station:{station_id}",
            "kind": "station",
            "label": str(station.get("display_name") or station_id),
            "selection_status": "AVAILABLE_FOR_PRESENTATION_FOCUS",
            "scene_mode": "interior_follow",
            "focus_room_id": room_id or None,
            "exterior_visual_role": None,
            "source_ids": [station_id, room_id] if room_id else [station_id],
            "inspection": {
                "room_id": room_id or None,
                "seat_role_ids": copy.deepcopy(station.get("seat_role_ids", [])),
                "placement_authority": station.get("placement_authority"),
            },
            "truth_boundary": "Station selection changes presentation focus only and does not seat or move authoritative crew.",
        }))
    for station in scene.get("unresolved_station_anchors", []):
        if not isinstance(station, dict) or not station.get("station_id"):
            continue
        station_id = str(station["station_id"])
        rows.append(_target({
            "target_id": f"station:{station_id}",
            "kind": "station_hold",
            "label": str(station.get("display_name") or station_id),
            "selection_status": "HOLD_NO_PINNED_ROOM_FOR_STATION",
            "scene_mode": "ship_cutaway",
            "focus_room_id": None,
            "exterior_visual_role": None,
            "source_ids": [station_id],
            "inspection": {
                "room_id": None,
                "seat_role_ids": copy.deepcopy(station.get("seat_role_ids", [])),
                "placement_authority": station.get("placement_authority"),
            },
            "truth_boundary": "The missing room mapping remains visible as a hold; the explorer does not invent a room for the station.",
        }))
    return rows


def _interior_system_targets(scene: dict[str, Any]) -> list[dict[str, Any]]:
    rooms_by_system: dict[str, list[str]] = {}
    labels: dict[str, str] = {}
    for room in scene.get("rooms", []):
        if not isinstance(room, dict) or not room.get("room_id"):
            continue
        room_id = str(room["room_id"])
        for raw_system in room.get("ship_system_bindings", []):
            system_id = str(raw_system)
            rooms_by_system.setdefault(system_id, []).append(room_id)
            labels.setdefault(system_id, system_id.replace("_", " ").title())
    rows: list[dict[str, Any]] = []
    for system_id in sorted(rooms_by_system):
        room_ids = sorted(set(rooms_by_system[system_id]))
        rows.append(_target({
            "target_id": f"interior-system:{system_id}",
            "kind": "interior_system_binding",
            "label": labels[system_id],
            "selection_status": "AVAILABLE_FOR_ABSTRACT_SYSTEM_INSPECTION",
            "scene_mode": "interior_follow",
            "focus_room_id": room_ids[0] if room_ids else None,
            "exterior_visual_role": None,
            "source_ids": [system_id, *room_ids],
            "inspection": {
                "system_id": system_id,
                "bound_room_ids": room_ids,
                "hardware_specificity": "ABSTRACT_REGISTERED_SYSTEM_BINDING_NOT_HARDWARE_REPLICA",
            },
            "truth_boundary": "The inspector exposes a registered room/system binding and abstract machinery animation only; it does not claim physical hardware layout or live system state.",
        }))
    return rows


def _portal_targets(interior: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for portal in interior.get("portal_actors", []):
        if not isinstance(portal, dict) or not portal.get("portal_id"):
            continue
        a = str(portal.get("from_room_id") or "")
        b = str(portal.get("to_room_id") or "")
        rows.append(_target({
            "target_id": f"portal:{portal['portal_id']}",
            "kind": "presentation_portal",
            "label": f"Portal · {a.replace('_', ' ')} ↔ {b.replace('_', ' ')}",
            "selection_status": "AVAILABLE_FOR_PRESENTATION_INSPECTION",
            "scene_mode": "ship_cutaway",
            "focus_room_id": a or None,
            "exterior_visual_role": None,
            "source_ids": [str(portal["portal_id"]), a, b],
            "inspection": {
                "from_room_id": a,
                "to_room_id": b,
                "travel_time_minutes": portal.get("travel_time_minutes"),
                "travel_time_authority": portal.get("travel_time_authority"),
                "animation_semantics": portal.get("animation_semantics"),
            },
            "truth_boundary": "Portal selection inspects a graph edge and animation actor; it does not open an authoritative physical door.",
        }))
    return rows


def _exterior_targets(exterior: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for actor in exterior.get("system_actors", []):
        if not isinstance(actor, dict) or not actor.get("system_id"):
            continue
        system_id = str(actor["system_id"])
        rows.append(_target({
            "target_id": f"exterior-system:{system_id}",
            "kind": "exterior_system_actor",
            "label": str(actor.get("display_name") or system_id),
            "selection_status": "AVAILABLE_FOR_CAPABILITY_INSPECTION",
            "scene_mode": "exterior_orbit",
            "focus_room_id": None,
            "exterior_visual_role": actor.get("visual_role"),
            "source_ids": [system_id],
            "inspection": {
                "system_id": system_id,
                "category": actor.get("category"),
                "criticality": actor.get("criticality"),
                "visual_role": actor.get("visual_role"),
                "declared_functions": copy.deepcopy(actor.get("declared_functions", [])),
                "declared_dependencies": copy.deepcopy(actor.get("declared_dependencies", [])),
                "operation_state": actor.get("operation_state"),
                "animation_semantics": actor.get("animation_semantics"),
            },
            "truth_boundary": "Exterior-system selection inspects a declared capability actor only; it does not activate, execute or certify that operation.",
        }))
    for module in exterior.get("module_actors", []):
        if not isinstance(module, dict) or not module.get("module_id"):
            continue
        module_id = str(module["module_id"])
        rows.append(_target({
            "target_id": f"module:{module_id}",
            "kind": "declared_module_actor",
            "label": module_id.replace("_", " ").title(),
            "selection_status": "AVAILABLE_FOR_PRESENTATION_INSPECTION",
            "scene_mode": "exterior_orbit",
            "focus_room_id": None,
            "exterior_visual_role": "systems",
            "source_ids": [module_id],
            "inspection": {
                "module_id": module_id,
                "functions": copy.deepcopy(module.get("functions", [])),
                "contains_rooms": copy.deepcopy(module.get("contains_rooms", [])),
                "geometry_authority": module.get("geometry_authority"),
            },
            "truth_boundary": "Module selection exposes declared architecture and presentation placement only; it does not establish vehicle dimensions or mechanism state.",
        }))
    return rows


def build_interactive_exploration(
    scene: dict[str, Any],
    interior: dict[str, Any],
    exterior: dict[str, Any],
    cinematic: dict[str, Any],
) -> dict[str, Any]:
    _validate_sources(scene, interior, exterior, cinematic)
    targets = [
        *_room_targets(scene),
        *_station_targets(scene),
        *_interior_system_targets(scene),
        *_portal_targets(interior),
        *_exterior_targets(exterior),
    ]
    ids = [str(row["target_id"]) for row in targets]
    if len(ids) != len(set(ids)):
        raise ValueError("interactive exploration target ids must be unique")
    targets.sort(key=lambda row: (str(row.get("kind")), str(row.get("label")), str(row.get("target_id"))))
    default_target_id = "room:command_deck" if "room:command_deck" in ids else (targets[0]["target_id"] if targets else None)
    packet = {
        "schema": "axm.interactive-exploration-presentation.v1",
        "version": EXPLORATION_VERSION,
        "source_scene_hash": scene.get("scene_hash"),
        "source_interior_animation_hash": interior.get("animation_hash"),
        "source_exterior_animation_hash": exterior.get("animation_hash"),
        "source_cinematic_director_hash": cinematic.get("director_hash"),
        "target_count": len(targets),
        "targets": targets,
        "default_target_id": default_target_id,
        "follow_modes": [
            {
                "id": "director",
                "label": "Causal director",
                "semantics": "FOLLOW_IMMUTABLE_CUE_DIRECTOR",
            },
            {
                "id": "selected_target",
                "label": "Selected target",
                "semantics": "FOLLOW_USER_PRESENTATION_SELECTION_ONLY",
            },
            {
                "id": "active_procedure",
                "label": "Active procedure",
                "semantics": "FOLLOW_EXISTING_PROCEDURE_REHEARSAL_TRACK_ONLY",
            },
            {
                "id": "active_event",
                "label": "Active event",
                "semantics": "FOLLOW_CURRENT_IMMUTABLE_REPLAY_EVENT_ONLY",
            },
        ],
        "interaction_capabilities": {
            "select_from_target_catalog": True,
            "cycle_targets": True,
            "tap_registered_room_in_cutaway": True,
            "inspect_source_metadata": True,
            "follow_selected_presentation_target": True,
            "follow_existing_procedure_rehearsal": True,
            "follow_current_event": True,
            "execute_or_mutate": False,
        },
        "authority": "read_only_interactive_exploration_presentation",
        "truth_boundary": (
            "Explorer selection, target cycling, room taps, follow modes and metadata inspection alter presentation focus only. They do not move authoritative crew/robotics, open doors, operate systems, retarget immutable events, change mission time, change resources or create physical geometry/hardware claims."
        ),
        "renderer_may_select_presentation_target": True,
        "renderer_may_inspect_declared_source_metadata": True,
        "renderer_may_follow_existing_presentation_context": True,
        "renderer_may_change_authoritative_selection": False,
        "renderer_may_retarget_event": False,
        "renderer_may_move_authoritative_crew": False,
        "renderer_may_move_authoritative_robotics": False,
        "renderer_may_open_authoritative_doors": False,
        "renderer_may_execute_action": False,
        "renderer_may_execute_operation": False,
        "renderer_may_modify_world_state": False,
        "renderer_may_modify_resources": False,
        "renderer_may_advance_mission_time": False,
        "renderer_may_claim_physical_geometry": False,
        "renderer_may_claim_physical_hardware": False,
        "renderer_may_change_truth_labels": False,
    }
    packet["exploration_hash"] = _hash(packet, "AXM-INTERACTIVE-EXPLORATION-PRESENTATION-V1")
    return packet
