from __future__ import annotations

import copy
import hashlib
import json
from collections import deque
from typing import Any


ANIMATION_VERSION = "0.13.0-candidate"

ROOM_ACTIVITY_CHANNELS: dict[str, tuple[str, ...]] = {
    "command": ("console_scan", "station_status_pulse", "shared_map_sweep", "command_light_breathe"),
    "transit": ("guide_light_chase", "portal_status_pulse", "corridor_depth_sweep"),
    "crew_life": ("service_light_pulse", "table_console_idle", "environment_status_breathe"),
    "technical": ("equipment_status_pulse", "maintenance_indicator_sweep", "thermal_visual_cycle", "power_bus_visual_chase"),
    "analysis": ("hologram_scan", "sensor_trace_sweep", "probe_status_pulse", "evidence_panel_cycle"),
    "personal": ("low_ambient_pulse", "artifact_display_shimmer", "sleep_cycle_light_breathe"),
    "personal_machine": ("compute_activity_bars", "artifact_display_shimmer", "offline_analysis_sweep"),
}

RESOURCE_VISUAL_MAP = {
    "reactor_reserve_percent": ("engineering", "command_deck"),
    "sensor_health_percent": ("research_strategy", "command_deck"),
    "hull_integrity_percent": ("central_corridor", "command_deck"),
    "fuel_percent": ("engineering", "command_deck"),
    "heat_percent": ("engineering",),
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any, domain: str) -> str:
    return hashlib.sha256(f"{domain}|{_canonical(value)}".encode("utf-8")).hexdigest()


def _scene_room_index(scene: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if scene.get("schema") != "axm.low-graphic-3d-scene.v1":
        raise ValueError("unsupported low-graphic 3D scene")
    rows = scene.get("rooms", [])
    if not isinstance(rows, list) or not rows:
        raise ValueError("low-graphic 3D scene has no rooms")
    rooms = {str(row["room_id"]): row for row in rows if isinstance(row, dict) and row.get("room_id")}
    if len(rooms) != len(rows):
        raise ValueError("low-graphic 3D scene contains invalid or duplicate rooms")
    return rooms


def _graph(scene: dict[str, Any], rooms: dict[str, dict[str, Any]]) -> dict[str, set[str]]:
    graph = {room_id: set() for room_id in rooms}
    edges = scene.get("room_edges", [])
    if not isinstance(edges, list):
        raise ValueError("scene room edges must be a list")
    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError("scene room edge must be an object")
        a = str(edge.get("from_room_id") or "")
        b = str(edge.get("to_room_id") or "")
        if a not in rooms or b not in rooms or a == b:
            raise ValueError("scene room edge references invalid rooms")
        graph[a].add(b)
        graph[b].add(a)
    return graph


def _shortest_path(graph: dict[str, set[str]], start: str, target: str) -> list[str]:
    if start not in graph or target not in graph:
        return []
    queue: deque[tuple[str, list[str]]] = deque([(start, [start])])
    visited = {start}
    while queue:
        room, path = queue.popleft()
        if room == target:
            return path
        for neighbor in sorted(graph[room]):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append((neighbor, path + [neighbor]))
    return []


def _director_walkthrough(scene: dict[str, Any], rooms: dict[str, dict[str, Any]], graph: dict[str, set[str]]) -> dict[str, Any]:
    default_room = "command_deck" if "command_deck" in rooms else sorted(rooms)[0]
    ordered_targets = sorted(
        rooms,
        key=lambda room_id: (
            int(rooms[room_id].get("presentation_position", {}).get("graph_depth", 0)),
            int(rooms[room_id].get("presentation_position", {}).get("lane_index", 0)),
            room_id,
        ),
    )
    route = [default_room]
    current = default_room
    for target in ordered_targets:
        if target == current:
            continue
        segment = _shortest_path(graph, current, target)
        if not segment:
            raise ValueError("director walkthrough cannot traverse disconnected scene graph")
        route.extend(segment[1:])
        current = target
    return {
        "track_id": "director_walkthrough:registered_interior_graph:v1",
        "route_rooms": route,
        "movement_semantics": "CAMERA_ONLY_PRESENTATION_WALKTHROUGH",
        "may_move_authoritative_crew": False,
        "may_claim_recorded_travel": False,
    }


def _procedure_index(procedure_catalog: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if procedure_catalog is None:
        return {}
    if procedure_catalog.get("schema") != "axm.failure-procedure-catalog.v1":
        raise ValueError("unsupported failure procedure catalog")
    return {str(row.get("source_failure_id")): row for row in procedure_catalog.get("procedures", []) if isinstance(row, dict) and row.get("source_failure_id")}


def _room_activity_profiles(rooms: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for room_id in sorted(rooms):
        room = rooms[room_id]
        room_type = str(room.get("room_type") or "unknown")
        channels = ROOM_ACTIVITY_CHANNELS.get(room_type, ("ambient_room_activity", "system_binding_pulses"))
        systems = sorted({str(v) for v in room.get("ship_system_bindings", []) if v})
        rows.append({
            "activity_id": f"room-activity:{room_id}:v1",
            "room_id": room_id,
            "room_type": room_type,
            "activity_channels": list(channels),
            "system_binding_ids": systems,
            "abstract_machine_actor_count": min(6, max(1, len(systems))),
            "animation_semantics": "ABSTRACT_STATUS_AND_AMBIENT_MOTION_NOT_PHYSICAL_HARDWARE_MODEL",
            "may_claim_physical_hardware": False,
            "may_modify_system_state": False,
        })
    return rows


def _portal_actors(scene: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for edge in scene.get("room_edges", []):
        a = str(edge.get("from_room_id"))
        b = str(edge.get("to_room_id"))
        pair = sorted((a, b))
        rows.append({
            "portal_id": f"presentation-portal:{pair[0]}:{pair[1]}:v1",
            "from_room_id": pair[0],
            "to_room_id": pair[1],
            "travel_time_minutes": edge.get("travel_time_minutes"),
            "travel_time_authority": edge.get("travel_time_authority"),
            "motion": "presentation_slide_open_hold_close",
            "open_trigger_sources": ["selected_rehearsal_route_crossing", "director_camera_walkthrough"],
            "animation_semantics": "PRESENTATION_PORTAL_NOT_A_PHYSICAL_DOOR_DESIGN_OR_AUTHORITATIVE_DOOR_STATE",
            "may_open_authoritative_door": False,
            "may_claim_physical_door_design": False,
        })
    rows.sort(key=lambda row: row["portal_id"])
    return rows


def _crew_reenactment_tracks(scene: dict[str, Any], procedure_catalog: dict[str, Any] | None) -> list[dict[str, Any]]:
    procedures = _procedure_index(procedure_catalog)
    rows: list[dict[str, Any]] = []
    for route in scene.get("rehearsal_routes", []):
        if not isinstance(route, dict) or not route.get("source_failure_id"):
            continue
        failure_id = str(route["source_failure_id"])
        procedure = procedures.get(failure_id, {})
        path = [str(v) for v in route.get("route_rooms", []) if v]
        rows.append({
            "track_id": f"crew-reenactment:{failure_id}:v1",
            "source_failure_id": failure_id,
            "source_system_id": route.get("source_system_id"),
            "source_role_id": procedure.get("primary_role_id"),
            "source_station_id": procedure.get("primary_station_id"),
            "route_rooms": path,
            "target_room_id": route.get("target_room_id"),
            "access_status": route.get("access_status"),
            "movement_semantics": "PROCEDURE_REHEARSAL_MARKER_ONLY_NOT_AUTHORITATIVE_CREW_POSITION",
            "may_move_authoritative_crew": False,
            "may_execute_repair": False,
            "may_claim_fault_active": False,
        })
    rows.sort(key=lambda row: row["track_id"])
    return rows


def _resource_visual_channels(scene: dict[str, Any], rooms: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    resources = scene.get("source_runtime_resource_snapshot", {})
    resources = resources if isinstance(resources, dict) else {}
    rows: list[dict[str, Any]] = []
    for resource_id, room_ids in RESOURCE_VISUAL_MAP.items():
        if resource_id not in resources:
            continue
        targets = [room_id for room_id in room_ids if room_id in rooms]
        rows.append({
            "resource_id": resource_id,
            "source_value": copy.deepcopy(resources[resource_id]),
            "target_room_ids": targets,
            "visual_semantics": "COPIED_READ_ONLY_RESOURCE_INDICATOR",
            "may_modify_resource": False,
            "may_infer_missing_resource": False,
        })
    return rows


def build_living_interior_animation(scene: dict[str, Any], *, procedure_catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    rooms = _scene_room_index(scene)
    graph = _graph(scene, rooms)
    packet = {
        "schema": "axm.living-interior-animation.v1",
        "version": ANIMATION_VERSION,
        "source_scene_hash": scene.get("scene_hash"),
        "source_scene_version": scene.get("version"),
        "interior_id": scene.get("interior_id"),
        "room_activity_profiles": _room_activity_profiles(rooms),
        "portal_actors": _portal_actors(scene),
        "crew_reenactment_tracks": _crew_reenactment_tracks(scene, procedure_catalog),
        "director_walkthrough": _director_walkthrough(scene, rooms, graph),
        "resource_visual_channels": _resource_visual_channels(scene, rooms),
        "animation_profile": {
            "room_ambience": "room_type_specific_low_pixel_motion",
            "portals": "graph_edge_transition_animation",
            "crew": "billboard_reenactment_tracks_plus_station_idle_motion",
            "machinery": "abstract_system_binding_activity_not_hardware_replica",
            "environment": "presentation_only_light_particles_and_status_sweeps",
            "camera": "bounded_room_to_room_follow_and_walkthrough",
            "reduced_motion_supported": True,
            "external_dependencies": [],
        },
        "authority": "read_only_living_interior_presentation",
        "truth_boundary": "Doors, machinery, environmental effects, crew walking markers, and camera travel are presentation actors over registered rooms, graph edges, system bindings, resource snapshots, and procedure rehearsal routes. They are not authoritative crew positions, physical hardware models, real door states, fault truth, repair execution, or resource mutation.",
        "renderer_may_animate_room_ambience": True,
        "renderer_may_animate_portals": True,
        "renderer_may_animate_crew_reenactment": True,
        "renderer_may_animate_abstract_machinery": True,
        "renderer_may_open_authoritative_doors": False,
        "renderer_may_move_authoritative_crew": False,
        "renderer_may_claim_physical_hardware": False,
        "renderer_may_claim_fault_active_from_rehearsal": False,
        "renderer_may_execute_repair": False,
        "renderer_may_modify_runtime": False,
        "renderer_may_modify_resources": False,
        "renderer_may_change_truth_labels": False,
    }
    packet["animation_hash"] = _hash(packet, "AXM-LIVING-INTERIOR-ANIMATION-V1")
    return packet
