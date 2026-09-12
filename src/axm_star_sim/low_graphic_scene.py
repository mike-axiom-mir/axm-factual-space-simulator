from __future__ import annotations

import copy
import hashlib
import json
from collections import deque
from typing import Any

from .damage_topology import STATION_ROOM_MAP


SCENE_VERSION = "0.12.0-candidate"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any, domain: str) -> str:
    return hashlib.sha256(f"{domain}|{_canonical(value)}".encode("utf-8")).hexdigest()


def _select_default_interior(registry: dict[str, Any]) -> dict[str, Any]:
    if registry.get("schema") != "axm.ship-interior-archetype-registry.v1":
        raise ValueError("unsupported ship interior registry")
    rows = registry.get("interiors", [])
    if not isinstance(rows, list) or not rows:
        raise ValueError("ship interior registry has no interiors")
    wanted = registry.get("default_interior_id")
    for row in rows:
        if isinstance(row, dict) and row.get("id") == wanted:
            return row
    raise ValueError("default ship interior not found")


def _room_index(interior: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = interior.get("rooms", [])
    if not isinstance(rows, list) or not rows:
        raise ValueError("interior has no rooms")
    return {
        str(row["id"]): row
        for row in rows
        if isinstance(row, dict) and row.get("id")
    }


def _room_graph(interior: dict[str, Any]) -> dict[str, set[str]]:
    rooms = _room_index(interior)
    graph = {room_id: set() for room_id in rooms}
    for room_id, row in rooms.items():
        adjacent = row.get("adjacent_rooms", [])
        if not isinstance(adjacent, list):
            raise ValueError(f"room adjacency must be a list: {room_id}")
        for raw_neighbor in adjacent:
            neighbor = str(raw_neighbor)
            if neighbor not in rooms:
                raise ValueError(f"room references unknown adjacent room: {room_id}->{neighbor}")
            graph[room_id].add(neighbor)
            graph[neighbor].add(room_id)
    return graph


def _presentation_layout(interior: dict[str, Any]) -> dict[str, dict[str, float | int]]:
    """Build stable graph-derived coordinates that explicitly are not physical geometry."""
    rooms = _room_index(interior)
    graph = _room_graph(interior)
    start = str(interior.get("default_room_id") or "")
    if start not in rooms:
        raise ValueError("default interior room is missing")

    depth: dict[str, int] = {start: 0}
    queue: deque[str] = deque([start])
    while queue:
        room = queue.popleft()
        for neighbor in sorted(graph[room]):
            if neighbor not in depth:
                depth[neighbor] = depth[room] + 1
                queue.append(neighbor)
    if len(depth) != len(rooms):
        raise ValueError("interior graph is not fully connected")

    layers: dict[int, list[str]] = {}
    for room_id, level in depth.items():
        layers.setdefault(level, []).append(room_id)

    layout: dict[str, dict[str, float | int]] = {}
    for level in sorted(layers):
        room_ids = sorted(layers[level])
        center = (len(room_ids) - 1) / 2.0
        for index, room_id in enumerate(room_ids):
            layout[room_id] = {
                "graph_depth": level,
                "lane_index": index,
                "lane_count": len(room_ids),
                "x": round((index - center) * 1.65, 4),
                "y": round(level * 1.28, 4),
                "z": round(level * 0.18, 4),
            }
    return layout


def _station_anchors(
    station_registry: dict[str, Any],
    rooms: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if station_registry.get("schema") != "axm.crew-station-display-registry.v1":
        raise ValueError("unsupported crew station registry")
    placed: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for station in station_registry.get("stations", []):
        if not isinstance(station, dict) or not station.get("id"):
            continue
        station_id = str(station["id"])
        room_id = STATION_ROOM_MAP.get(station_id)
        row = {
            "station_id": station_id,
            "display_name": station.get("display_name", station_id),
            "seat_role_ids": sorted(
                {str(v) for v in station.get("seat_role_ids", []) if v}
            ),
            "room_id": room_id,
            "placement_authority": (
                "existing_damage_topology_station_room_map_presentation_anchor"
                if room_id in rooms
                else "NO_PINNED_ROOM_FOR_STATION"
            ),
            "may_move_authoritative_crew": False,
        }
        if room_id in rooms:
            placed.append(row)
        else:
            unresolved.append(row)
    placed.sort(key=lambda row: (str(row["room_id"]), row["station_id"]))
    unresolved.sort(key=lambda row: row["station_id"])
    return placed, unresolved


def _rehearsal_routes(
    damage_topology_catalog: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if damage_topology_catalog is None:
        return []
    if damage_topology_catalog.get("schema") != "axm.damage-topology-catalog.v1":
        raise ValueError("unsupported damage topology catalog")
    rows: list[dict[str, Any]] = []
    for topology in damage_topology_catalog.get("topologies", []):
        if not isinstance(topology, dict) or not topology.get("source_failure_id"):
            continue
        access = topology.get("access", {}) if isinstance(topology.get("access"), dict) else {}
        preferred = (
            access.get("preferred_room_path", {})
            if isinstance(access.get("preferred_room_path"), dict)
            else {}
        )
        path = [str(v) for v in preferred.get("rooms", []) if v]
        rows.append({
            "source_failure_id": str(topology.get("source_failure_id")),
            "source_system_id": topology.get("source_system_id"),
            "source_criticality": topology.get("source_criticality"),
            "route_rooms": path,
            "target_room_id": preferred.get("target_room_id"),
            "access_status": access.get("status"),
            "animation_semantics": "REHEARSAL_ROUTE_ONLY_NOT_ACTIVE_FAULT_STATE",
            "may_claim_fault_active": False,
            "may_execute_repair": False,
        })
    rows.sort(key=lambda row: row["source_failure_id"])
    return rows


def build_low_graphic_3d_scene(
    operations_context: dict[str, Any],
    station_registry: dict[str, Any],
    interior_registry: dict[str, Any],
    *,
    damage_topology_catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if operations_context.get("schema") != "axm.living-operations-context.v1":
        raise ValueError("unsupported operations context")
    interior = _select_default_interior(interior_registry)
    rooms = _room_index(interior)
    graph = _room_graph(interior)
    layout = _presentation_layout(interior)
    stations, unresolved_stations = _station_anchors(station_registry, rooms)

    room_rows: list[dict[str, Any]] = []
    for room_id in sorted(rooms):
        source = rooms[room_id]
        room_rows.append({
            "room_id": room_id,
            "display_name": source.get("display_name", room_id),
            "room_type": source.get("room_type", "unknown"),
            "purpose": copy.deepcopy(source.get("purpose", [])),
            "adjacent_rooms": sorted(graph[room_id]),
            "ship_system_bindings": sorted(
                {str(v) for v in source.get("ship_system_bindings", []) if v}
            ),
            "presentation_position": layout[room_id],
            "position_authority": "presentation_only_graph_layout_not_physical_ship_geometry",
            "animation_channels": [
                "ambient_room_activity",
                "system_binding_pulses",
                "crew_marker_presence",
                "rehearsal_route_highlight",
            ],
            "may_claim_physical_dimensions": False,
            "may_claim_system_fault_active": False,
        })

    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    travel = interior.get("travel_time_minutes", {})
    travel = travel if isinstance(travel, dict) else {}
    for room_id in sorted(graph):
        for neighbor in sorted(graph[room_id]):
            edge = tuple(sorted((room_id, neighbor)))
            if edge in seen:
                continue
            seen.add(edge)
            key_a = f"{edge[0]}|{edge[1]}"
            key_b = f"{edge[1]}|{edge[0]}"
            raw_minutes = travel.get(key_a, travel.get(key_b))
            edges.append({
                "from_room_id": edge[0],
                "to_room_id": edge[1],
                "travel_time_minutes": raw_minutes,
                "travel_time_authority": (
                    "interior_registry"
                    if raw_minutes is not None
                    else "UNKNOWN_NOT_IN_REGISTRY"
                ),
                "animation_semantics": "presentation_path_only",
            })

    resources = operations_context.get("resources", {})
    resources = copy.deepcopy(resources) if isinstance(resources, dict) else {}
    packet = {
        "schema": "axm.low-graphic-3d-scene.v1",
        "version": SCENE_VERSION,
        "interior_id": interior.get("id"),
        "interior_version": interior.get("version"),
        "interior_display_name": interior.get("display_name"),
        "room_count": len(room_rows),
        "rooms": room_rows,
        "room_edges": edges,
        "station_count": len(stations),
        "station_anchors": stations,
        "unresolved_station_anchors": unresolved_stations,
        "rehearsal_routes": _rehearsal_routes(damage_topology_catalog),
        "source_runtime_resource_snapshot": resources,
        "source_turn": operations_context.get("source_turn"),
        "source_mission_time_hours": operations_context.get("source_mission_time_hours"),
        "camera_presets": [
            {"id": "ship_cutaway", "label": "Ship cutaway", "semantics": "isometric_graph_overview"},
            {"id": "interior_follow", "label": "Interior follow", "semantics": "room_and_rehearsal_route_focus"},
            {"id": "exterior_orbit", "label": "Exterior", "semantics": "decorative_ship_and_receipt_target_replay"},
            {"id": "legacy_bridge", "label": "Bridge", "semantics": "existing_low_pixel_bridge_renderer"},
        ],
        "animation_profile": {
            "framebuffer": [480, 270],
            "render_style": "low_pixel_2_5d_flat_shaded",
            "room_motion": "subpixel_free_integer_framebuffer_tween",
            "crew_motion": "billboard_markers_reenactment_only",
            "system_motion": "state_or_rehearsal_label_driven_visual_cues_only",
            "camera_motion": "bounded_presentation_choreography",
            "reduced_motion_supported": True,
            "external_dependencies": [],
        },
        "authority": "read_only_visual_projection",
        "truth_boundary": "Scene geometry, camera motion, crew markers, lighting, and rehearsal routes are presentation constructs over existing registries and receipts. They are not physical ship geometry, authoritative crew movement, active fault truth, repair execution, or world state.",
        "renderer_may_animate": True,
        "renderer_may_modify_runtime": False,
        "renderer_may_advance_mission_time": False,
        "renderer_may_execute_action": False,
        "renderer_may_move_authoritative_crew": False,
        "renderer_may_claim_fault_active_from_rehearsal": False,
        "renderer_may_clear_fault": False,
        "renderer_may_exit_safe_state": False,
        "renderer_may_apply_operational_release": False,
        "renderer_may_restore_resources": False,
        "renderer_may_change_truth_labels": False,
    }
    packet["scene_hash"] = _hash(packet, "AXM-LOW-GRAPHIC-3D-SCENE-V1")
    return packet
