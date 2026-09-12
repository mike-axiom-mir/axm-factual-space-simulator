from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .registry import data_path


class BridgeContractError(ValueError):
    pass


def _load(name: str) -> dict[str, Any]:
    return json.loads(data_path(name).read_text(encoding="utf-8"))


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_record(value: Any, domain: str) -> str:
    return hashlib.sha256(f"{domain}|{canonical_json(value)}".encode("utf-8")).hexdigest()


def load_bridge_contract() -> dict[str, Any]:
    return _load("bridge_experience_contract.json")


def load_bridge_archetype_registry() -> dict[str, Any]:
    return _load("bridge_archetype_registry.json")


def load_timeline_start_registry() -> dict[str, Any]:
    return _load("timeline_start_registry.json")


def load_crew_start_registry() -> dict[str, Any]:
    return _load("crew_start_registry.json")


def load_render_profile_registry() -> dict[str, Any]:
    return _load("bridge_render_profile_registry.json")


def load_interior_registry() -> dict[str, Any]:
    return _load("ship_interior_archetype_registry.json")


def load_ship_blueprint_registry() -> dict[str, Any]:
    return _load("ship_system_blueprint_registry.json")


def _index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in rows}


def registry_indexes() -> dict[str, dict[str, dict[str, Any]]]:
    return {
        "bridges": _index(load_bridge_archetype_registry()["archetypes"]),
        "timelines": _index(load_timeline_start_registry()["timeline_starts"]),
        "crews": _index(load_crew_start_registry()["crew_starts"]),
        "renderers": _index(load_render_profile_registry()["profiles"]),
        "interiors": _index(load_interior_registry()["interiors"]),
        "ship_blueprints": _index(load_ship_blueprint_registry()["blueprints"]),
    }


def resolve_start_package(
    bridge_archetype_id: str | None = None,
    timeline_start_id: str | None = None,
    crew_start_id: str | None = None,
    render_profile_id: str = "axm.render.paint-foundation.v1",
    interior_archetype_id: str | None = None,
    ship_blueprint_id: str | None = None,
) -> dict[str, Any]:
    bridge_registry = load_bridge_archetype_registry()
    timeline_registry = load_timeline_start_registry()
    crew_registry = load_crew_start_registry()
    indexes = registry_indexes()
    bridge_id = bridge_archetype_id or bridge_registry["default_archetype_id"]
    timeline_id = timeline_start_id or timeline_registry["default_timeline_start_id"]
    crew_id = crew_start_id or crew_registry["default_crew_start_id"]
    selected_crew = indexes["crews"].get(crew_id, {})
    interior_registry = load_interior_registry()
    blueprint_registry = load_ship_blueprint_registry()
    interior_id = interior_archetype_id or selected_crew.get("interior_archetype_id") or interior_registry["default_interior_id"]
    blueprint_id = ship_blueprint_id or selected_crew.get("ship_blueprint_id") or blueprint_registry["default_blueprint_id"]

    try:
        bridge = copy.deepcopy(indexes["bridges"][bridge_id])
        timeline = copy.deepcopy(indexes["timelines"][timeline_id])
        crew = copy.deepcopy(indexes["crews"][crew_id])
        renderer = copy.deepcopy(indexes["renderers"][render_profile_id])
        interior = copy.deepcopy(indexes["interiors"][interior_id])
        ship_blueprint = copy.deepcopy(indexes["ship_blueprints"][blueprint_id])
    except KeyError as exc:
        raise BridgeContractError(f"unknown start component: {exc.args[0]}") from exc

    allowed = timeline.get("allowed_bridge_archetypes", [])
    if allowed and bridge_id not in allowed and "*" not in allowed:
        raise BridgeContractError(f"timeline {timeline_id} does not permit bridge {bridge_id}")

    bridge_anchors = set(bridge["semantic_anchors"])
    for command in crew.get("command_presence", []):
        if command["seat_anchor"] not in bridge_anchors:
            raise BridgeContractError(f"crew command anchor missing from bridge: {command['seat_anchor']}")
    for member in crew.get("crew_roles", []):
        if member["station_anchor"] not in bridge_anchors:
            raise BridgeContractError(f"crew station anchor missing from bridge: {member['station_anchor']}")

    renderer_allowed = renderer.get("allowed_archetypes", [])
    if renderer_allowed and bridge_id not in renderer_allowed and "*" not in renderer_allowed:
        raise BridgeContractError(f"renderer {render_profile_id} does not permit bridge {bridge_id}")
    if renderer.get("changes_semantics"):
        raise BridgeContractError("a render profile may not declare semantic changes")
    if interior.get("bridge_archetype_id") != bridge_id:
        raise BridgeContractError(f"interior {interior_id} is not bound to bridge {bridge_id}")
    if interior.get("ship_blueprint_id") not in {None, blueprint_id}:
        raise BridgeContractError(f"interior {interior_id} is not bound to blueprint {blueprint_id}")
    if crew.get("ship_blueprint_id") not in {None, blueprint_id}:
        raise BridgeContractError(f"crew {crew_id} is not bound to blueprint {blueprint_id}")
    if ship_blueprint.get("bridge_archetype_id") != bridge_id:
        raise BridgeContractError(f"blueprint {blueprint_id} is not bound to bridge {bridge_id}")
    if ship_blueprint.get("interior_archetype_id") != interior_id:
        raise BridgeContractError(f"blueprint {blueprint_id} is not bound to interior {interior_id}")
    if ship_blueprint.get("crew_start_id") != crew_id:
        raise BridgeContractError(f"blueprint {blueprint_id} is not bound to crew {crew_id}")

    package = {
        "schema": "axm.ship-start-package.v1",
        "bridge_archetype": bridge,
        "timeline_start": timeline,
        "crew_start": crew,
        "ship_interior": interior,
        "ship_blueprint": ship_blueprint,
        "render_profile": renderer,
        "experience_contract": load_bridge_contract(),
    }
    package["start_package_receipt"] = sha256_record(package, "AXM-SHIP-START-PACKAGE-V1")
    return package


def pin_start_package_for_save(start_package: dict[str, Any]) -> dict[str, Any]:
    bridge = start_package["bridge_archetype"]
    timeline = start_package["timeline_start"]
    crew = start_package["crew_start"]
    renderer = start_package["render_profile"]
    interior = start_package["ship_interior"]
    ship_blueprint = start_package["ship_blueprint"]
    from .ship_blueprint import blueprint_commitment
    pin = {
        "schema": "axm.ship-start-pin.v1",
        "bridge_archetype_id": bridge["id"],
        "bridge_archetype_version": bridge["version"],
        "timeline_start_id": timeline["id"],
        "timeline_start_version": timeline["version"],
        "crew_start_id": crew["id"],
        "crew_start_version": crew["version"],
        "interior_archetype_id": interior["id"],
        "interior_archetype_version": interior["version"],
        "ship_blueprint_id": ship_blueprint["id"],
        "ship_blueprint_version": ship_blueprint["version"],
        "ship_blueprint_commitment": blueprint_commitment(ship_blueprint["id"]),
        "initial_render_profile_id": renderer["id"],
        "initial_render_profile_version": renderer["version"],
        "semantic_anchor_ids": list(bridge["semantic_anchors"]),
        "start_package_receipt": start_package["start_package_receipt"],
        "migration_policy": "immutable_semantics_new_versions_only",
    }
    pin["pin_receipt"] = sha256_record(pin, "AXM-SHIP-START-PIN-V1")
    return pin


def make_reconstruction_packet(
    start_pin: dict[str, Any],
    historical_state_hash: str,
    target_render_profile_id: str,
) -> dict[str, Any]:
    indexes = registry_indexes()
    bridge = indexes["bridges"].get(start_pin["bridge_archetype_id"])
    renderer = indexes["renderers"].get(target_render_profile_id)
    if bridge is None:
        raise BridgeContractError("pinned bridge archetype is unavailable")
    if bridge["version"] != start_pin["bridge_archetype_version"]:
        raise BridgeContractError("pinned bridge archetype version mismatch")
    if renderer is None:
        raise BridgeContractError("unknown target renderer")
    if renderer.get("changes_semantics"):
        raise BridgeContractError("target renderer attempts to change semantics")
    packet = {
        "schema": "axm.bridge-reconstruction-packet.v1",
        "bridge_archetype_id": bridge["id"],
        "bridge_archetype_version": bridge["version"],
        "semantic_anchor_ids": list(start_pin["semantic_anchor_ids"]),
        "historical_state_hash": historical_state_hash,
        "target_render_profile_id": renderer["id"],
        "target_render_profile_version": renderer["version"],
        "renderer_may_change": [
            "geometry_detail",
            "materials",
            "lighting",
            "animation",
            "character_detail",
            "camera_transitions",
            "sound",
            "environmental_effects",
        ],
        "renderer_may_not_change": [
            "semantic_anchor_identity",
            "station_role",
            "command_presence",
            "dominant_world_view_role",
            "historical_state",
            "recorded_crew_actions",
        ],
    }
    packet["reconstruction_receipt"] = sha256_record(packet, "AXM-BRIDGE-RECONSTRUCTION-V1")
    return packet


def validate_layout_packet(
    layout: dict[str, Any],
    start_pin: dict[str, Any],
) -> dict[str, Any]:
    contract = load_bridge_contract()
    required = contract["required_in_every_playable_vessel"]
    failures: list[str] = []

    if layout.get("experience_type") != "inhabited_vessel_interior":
        failures.append("experience_type must be inhabited_vessel_interior")
    if not layout.get("spatial_room_identity"):
        failures.append("spatial room identity missing")
    if not layout.get("dominant_world_view"):
        failures.append("dominant world view missing")
    if not layout.get("visible_command_presence"):
        failures.append("visible command presence missing")
    if not layout.get("visible_crew_presence"):
        failures.append("visible crew presence missing")
    if not layout.get("diegetic_controls"):
        failures.append("diegetic controls missing")
    if layout.get("primary_interface_pattern") == "generic_website_dashboard":
        failures.append("generic website dashboard cannot be the primary experience")
    if layout.get("room_context_survives_station_focus") is not True:
        failures.append("station focus loses room context")
    if layout.get("low_fidelity_survival") is not True:
        failures.append("layout cannot survive low fidelity")

    supplied_anchors = set(layout.get("semantic_anchor_ids", []))
    expected_anchors = set(start_pin["semantic_anchor_ids"])
    missing = sorted(expected_anchors - supplied_anchors)
    if missing:
        failures.append(f"missing pinned semantic anchors: {missing}")

    forward_share = float(layout.get("dominant_world_view_share", 0.0))
    if forward_share < 0.42:
        failures.append("dominant world view occupies less than the first bridge minimum")

    forbidden = set(contract["forbidden_regressions"])
    declared = set(layout.get("declared_patterns", []))
    collisions = sorted(forbidden & declared)
    if collisions:
        failures.append(f"forbidden regression patterns declared: {collisions}")

    result = {
        "schema": "axm.bridge-layout-validation.v1",
        "valid": not failures,
        "failures": failures,
        "bridge_archetype_id": start_pin["bridge_archetype_id"],
        "bridge_archetype_version": start_pin["bridge_archetype_version"],
        "checked_anchor_count": len(expected_anchors),
    }
    result["validation_receipt"] = sha256_record(result, "AXM-BRIDGE-LAYOUT-VALIDATION-V1")
    return result


def first_bridge_reference_layout() -> dict[str, Any]:
    package = resolve_start_package()
    pin = pin_start_package_for_save(package)
    return {
        "schema": "axm.bridge-layout-packet.v1",
        "experience_type": "inhabited_vessel_interior",
        "spatial_room_identity": True,
        "dominant_world_view": True,
        "dominant_world_view_share": 0.52,
        "visible_command_presence": True,
        "visible_crew_presence": True,
        "diegetic_controls": True,
        "room_context_survives_station_focus": True,
        "low_fidelity_survival": True,
        "primary_interface_pattern": "bridge_room",
        "semantic_anchor_ids": list(pin["semantic_anchor_ids"]),
        "declared_patterns": ["paint_capable", "renderer_replaceable", "crew_station_highlights"],
        "start_pin": pin,
    }
