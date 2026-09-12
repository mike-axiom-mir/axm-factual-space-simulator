from __future__ import annotations

import copy
import hashlib
import json
from collections import deque
from typing import Any

TOPOLOGY_VERSION = "0.6.0-candidate"

STATION_ROOM_MAP = {
    "command_duet": "command_deck",
    "navigation_station": "command_deck",
    "engineering_station": "engineering",
    "science_station": "research_strategy",
    "communications_station": "command_deck",
    # The current interior has no dedicated medical room. Keep that absence visible.
    "medical_station": None,
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any, domain: str) -> str:
    return hashlib.sha256(f"{domain}|{_canonical(value)}".encode("utf-8")).hexdigest()


def _select_default(registry: dict[str, Any], list_key: str, default_key: str, item_id_key: str = "id") -> dict[str, Any]:
    rows = registry.get(list_key, [])
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{list_key} must contain at least one entry")
    wanted = registry.get(default_key)
    if wanted is None and len(rows) == 1:
        return rows[0]
    for row in rows:
        if isinstance(row, dict) and row.get(item_id_key) == wanted:
            return row
    raise ValueError(f"default {default_key} not found in {list_key}")


def _blueprint(registry: dict[str, Any]) -> dict[str, Any]:
    if registry.get("schema") != "axm.ship-system-blueprint-registry.v1":
        raise ValueError("unsupported ship blueprint registry")
    return _select_default(registry, "blueprints", "default_blueprint_id")


def _interior(registry: dict[str, Any]) -> dict[str, Any]:
    if registry.get("schema") != "axm.ship-interior-archetype-registry.v1":
        raise ValueError("unsupported ship interior registry")
    return _select_default(registry, "interiors", "default_interior_id")


def _system_index(blueprint: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = blueprint.get("systems", [])
    if not isinstance(rows, list):
        raise ValueError("blueprint systems must be a list")
    return {str(row["id"]): row for row in rows if isinstance(row, dict) and row.get("id")}


def _room_index(interior: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = interior.get("rooms", [])
    if not isinstance(rows, list):
        raise ValueError("interior rooms must be a list")
    return {str(row["id"]): row for row in rows if isinstance(row, dict) and row.get("id")}


def _room_graph(interior: dict[str, Any]) -> dict[str, set[str]]:
    rooms = _room_index(interior)
    graph = {room_id: set() for room_id in rooms}
    for room_id, row in rooms.items():
        for neighbor in row.get("adjacent_rooms", []):
            neighbor = str(neighbor)
            if neighbor in graph:
                graph[room_id].add(neighbor)
                graph[neighbor].add(room_id)
    return graph


def _travel_minutes(interior: dict[str, Any], a: str, b: str) -> float | None:
    times = interior.get("travel_time_minutes", {})
    if not isinstance(times, dict):
        return None
    raw = times.get(f"{a}|{b}", times.get(f"{b}|{a}"))
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _shortest_room_path(interior: dict[str, Any], start: str, target: str) -> dict[str, Any] | None:
    graph = _room_graph(interior)
    if start not in graph or target not in graph:
        return None
    queue: deque[tuple[str, list[str], float, bool]] = deque([(start, [start], 0.0, False)])
    visited = {start}
    while queue:
        room, path, minutes, has_unknown_time = queue.popleft()
        if room == target:
            return {
                "rooms": path,
                "travel_minutes": None if has_unknown_time else minutes,
                "travel_time_status": "UNKNOWN_EDGE_TIME_PRESENT" if has_unknown_time else "KNOWN_FROM_INTERIOR_REGISTRY",
            }
        for neighbor in sorted(graph[room]):
            if neighbor in visited:
                continue
            edge_minutes = _travel_minutes(interior, room, neighbor)
            visited.add(neighbor)
            queue.append(
                (
                    neighbor,
                    path + [neighbor],
                    minutes + (edge_minutes or 0.0),
                    has_unknown_time or edge_minutes is None,
                )
            )
    return None


def _procedure_index(procedure_catalog: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(procedure_catalog, dict):
        return {}
    rows = procedure_catalog.get("procedures", [])
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("source_failure_id")): row
        for row in rows
        if isinstance(row, dict) and row.get("source_failure_id")
    }


def _maintenance_capabilities(blueprint: dict[str, Any], room_interactions: dict[str, Any]) -> dict[str, Any]:
    systems = _system_index(blueprint)
    interactions = room_interactions.get("interactions", []) if isinstance(room_interactions, dict) else []
    interaction_ids = {
        str(row.get("id"))
        for row in interactions
        if isinstance(row, dict) and row.get("id")
    }
    return {
        "maintenance_system_present": "logistics_maintenance_fabrication" in systems,
        "repair_duration_estimator_present": "estimate_repair_duration" in interaction_ids,
        "fabrication_interaction_present": "fabricate_room_item" in interaction_ids,
        "component_specific_spares_status": "UNKNOWN_COMPONENT_SPECIFICITY_NOT_PINNED",
        "may_consume_spares": False,
        "may_fabricate_repair_part": False,
        "may_claim_repair_capability": False,
    }


def _room_bindings_for_system(system: dict[str, Any], interior: dict[str, Any]) -> tuple[list[str], list[str]]:
    known_rooms = _room_index(interior)
    mapped: set[str] = set()
    unresolved: set[str] = set()
    for raw in system.get("room_bindings", []):
        binding = str(raw)
        if binding == "all_pressurized_rooms":
            mapped.update(known_rooms)
        elif binding in known_rooms:
            mapped.add(binding)
        else:
            unresolved.add(binding)
    return sorted(mapped), sorted(unresolved)


def _direct_interfaces(system_id: str, interface_graph: dict[str, Any]) -> list[dict[str, Any]]:
    if interface_graph.get("schema") != "axm.ship-interface-graph.v1":
        raise ValueError("unsupported ship interface graph")
    out: list[dict[str, Any]] = []
    for edge in interface_graph.get("edges", []):
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        interface_type = str(edge.get("interface_type") or "unknown")
        if source == system_id:
            out.append(
                {
                    "direction": "outbound",
                    "neighbor_system_id": target,
                    "interface_type": interface_type,
                    "impact_semantics": "DIRECT_INTERFACE_ONLY_NOT_PROPAGATED_FAILURE",
                }
            )
        elif target == system_id:
            out.append(
                {
                    "direction": "inbound",
                    "neighbor_system_id": source,
                    "interface_type": interface_type,
                    "impact_semantics": "DIRECT_INTERFACE_ONLY_NOT_PROPAGATED_FAILURE",
                }
            )
    return sorted(out, key=lambda row: (row["direction"], row["neighbor_system_id"], row["interface_type"]))


def build_damage_topology(
    failure: dict[str, Any],
    blueprint_registry: dict[str, Any],
    interface_graph: dict[str, Any],
    interior_registry: dict[str, Any],
    room_interaction_registry: dict[str, Any],
    *,
    procedure: dict[str, Any] | None = None,
    index: int = 0,
) -> dict[str, Any]:
    if not isinstance(failure, dict):
        raise TypeError("failure must be an object")
    failure_id = str(failure.get("id") or "")
    system_id = str(failure.get("system_id") or "")
    if not failure_id or not system_id:
        raise ValueError("failure id and system_id are required")

    blueprint = _blueprint(blueprint_registry)
    interior = _interior(interior_registry)
    systems = _system_index(blueprint)
    system = systems.get(system_id)
    if system is None:
        return {
            "schema": "axm.damage-topology-view.v1",
            "version": TOPOLOGY_VERSION,
            "topology_id": f"damage-topology:{failure_id}:v1",
            "source_failure_index": index,
            "source_failure_id": failure_id,
            "source_system_id": system_id,
            "status": "HOLD_SOURCE_SYSTEM_NOT_IN_BLUEPRINT",
            "truth_boundary": "The failure names a system that is not present in the pinned ship blueprint.",
            "may_modify_runtime": False,
            "may_execute_repair": False,
            "may_clear_fault": False,
            "repair_verified": False,
        }

    mapped_rooms, unresolved_bindings = _room_bindings_for_system(system, interior)
    procedure_station = str(procedure.get("primary_station_id")) if isinstance(procedure, dict) and procedure.get("primary_station_id") else None
    origin_room = STATION_ROOM_MAP.get(procedure_station) if procedure_station else "engineering"
    if origin_room is None:
        access_status = "HOLD_NO_PINNED_STATION_ROOM"
        candidate_paths: list[dict[str, Any]] = []
        preferred = None
    else:
        candidate_paths = []
        for target_room in mapped_rooms:
            route = _shortest_room_path(interior, origin_room, target_room)
            if route is not None:
                candidate_paths.append({"target_room_id": target_room, **route})
        candidate_paths.sort(
            key=lambda row: (
                row["travel_minutes"] is None,
                float("inf") if row["travel_minutes"] is None else row["travel_minutes"],
                len(row["rooms"]),
                row["target_room_id"],
            )
        )
        preferred = candidate_paths[0] if candidate_paths else None
        if preferred and unresolved_bindings:
            access_status = "ACCESS_PATH_AVAILABLE_WITH_UNRESOLVED_EXTERNAL_BINDINGS"
        elif preferred:
            access_status = "ACCESS_PATH_AVAILABLE"
        elif unresolved_bindings:
            access_status = "HOLD_ONLY_UNMAPPED_OR_EXTERNAL_BINDINGS"
        else:
            access_status = "HOLD_NO_MAPPED_ACCESS_ROOM"

    topology = {
        "schema": "axm.damage-topology-view.v1",
        "version": TOPOLOGY_VERSION,
        "topology_id": f"damage-topology:{failure_id}:v1",
        "source_failure_index": index,
        "source_failure_id": failure_id,
        "source_system_id": system_id,
        "source_criticality": failure.get("criticality"),
        "source_command_level": failure.get("command_level"),
        "source_effects": copy.deepcopy(failure.get("effects", {})),
        "system": {
            "display_name": system.get("display_name", system_id),
            "category": system.get("category"),
            "criticality": system.get("criticality"),
            "declared_dependencies": list(system.get("dependencies", [])),
            "room_bindings": list(system.get("room_bindings", [])),
        },
        "direct_interfaces": _direct_interfaces(system_id, interface_graph),
        "impact_scope": "DIRECT_INTERFACE_NEIGHBORS_ONLY_NO_AUTOMATIC_FAILURE_PROPAGATION",
        "access": {
            "origin_station_id": procedure_station,
            "origin_room_id": origin_room,
            "mapped_target_rooms": mapped_rooms,
            "unresolved_or_external_bindings": unresolved_bindings,
            "candidate_room_paths": candidate_paths,
            "preferred_room_path": preferred,
            "status": access_status,
            "route_is_navigation_only": True,
        },
        "maintenance": _maintenance_capabilities(blueprint, room_interaction_registry),
        "procedure_link": {
            "procedure_id": procedure.get("procedure_id") if isinstance(procedure, dict) else None,
            "procedure_status": procedure.get("status") if isinstance(procedure, dict) else None,
            "link_semantics": "review_link_only_not_repair_execution",
        },
        "component_specificity": {
            "status": "SYSTEM_LEVEL_ONLY",
            "rule": "No valve, cable, bus branch, fastener, spare SKU, access panel, or repair part may be invented unless source-pinned in a later topology registry.",
        },
        "status": "TOPOLOGY_VIEW_AVAILABLE",
        "authority": "derived_damage_and_access_view_only",
        "may_modify_runtime": False,
        "may_execute_repair": False,
        "may_execute_automatic_response": False,
        "may_consume_spares": False,
        "may_fabricate_repair_part": False,
        "may_clear_fault": False,
        "may_claim_neighbor_failed": False,
        "repair_verified": False,
    }
    topology["topology_hash"] = _hash(topology, "AXM-DAMAGE-TOPOLOGY-V1")
    return topology


def build_damage_topology_catalog(
    failure_registry: dict[str, Any],
    blueprint_registry: dict[str, Any],
    interface_graph: dict[str, Any],
    interior_registry: dict[str, Any],
    room_interaction_registry: dict[str, Any],
    *,
    procedure_catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if failure_registry.get("schema") != "axm.ship-failure-mode-registry.v1":
        raise ValueError("unsupported failure registry")
    if room_interaction_registry.get("schema") != "axm.room-interaction-registry.v1":
        raise ValueError("unsupported room interaction registry")

    procedure_by_failure = _procedure_index(procedure_catalog)
    rows = []
    for index, failure in enumerate(failure_registry.get("failure_modes", [])):
        if not isinstance(failure, dict):
            continue
        failure_id = str(failure.get("id") or "")
        if not failure_id:
            continue
        rows.append(
            build_damage_topology(
                failure,
                blueprint_registry,
                interface_graph,
                interior_registry,
                room_interaction_registry,
                procedure=procedure_by_failure.get(failure_id),
                index=index,
            )
        )

    packet = {
        "schema": "axm.damage-topology-catalog.v1",
        "version": TOPOLOGY_VERSION,
        "blueprint_id": _blueprint(blueprint_registry).get("id"),
        "interior_id": _interior(interior_registry).get("id"),
        "topology_count": len(rows),
        "topologies": rows,
        "scope": "derived_system_interface_room_access_and_maintenance_view",
        "component_specificity": "SYSTEM_LEVEL_ONLY",
        "may_modify_runtime": False,
        "may_execute_repair": False,
        "may_execute_automatic_response": False,
        "may_consume_spares": False,
        "may_fabricate_repair_part": False,
        "may_clear_fault": False,
        "may_claim_neighbor_failed": False,
        "repair_verified": False,
    }
    packet["catalog_hash"] = _hash(packet, "AXM-DAMAGE-TOPOLOGY-CATALOG-V1")
    return packet


def verify_topology_packet(packet: dict[str, Any]) -> dict[str, Any]:
    expected = packet.get("topology_hash")
    if not isinstance(expected, str):
        return {"valid": False, "reason": "missing_topology_hash"}
    copy_packet = copy.deepcopy(packet)
    copy_packet.pop("topology_hash", None)
    observed = _hash(copy_packet, "AXM-DAMAGE-TOPOLOGY-V1")
    return {"valid": expected == observed, "expected": expected, "observed": observed}
