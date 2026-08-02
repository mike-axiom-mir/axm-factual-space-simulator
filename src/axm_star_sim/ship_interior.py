from __future__ import annotations

import copy
import hashlib
import json
import math
from collections import deque
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PACKAGE_ROOT / "data"


class ShipInteriorError(ValueError):
    pass


def _load(name: str) -> dict[str, Any]:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def domain_hash(value: Any, domain: str) -> str:
    return hashlib.sha256(f"{domain}|{canonical_json(value)}".encode("utf-8")).hexdigest()


def load_interior_registry() -> dict[str, Any]:
    return _load("ship_interior_archetype_registry.json")


def load_continuity_registry() -> dict[str, Any]:
    return _load("expedition_continuity_policy_registry.json")


def load_interaction_registry() -> dict[str, Any]:
    return _load("room_interaction_registry.json")


def load_item_policy() -> dict[str, Any]:
    return _load("interior_item_policy.json")


def _interior(interior_id: str | None = None) -> dict[str, Any]:
    registry = load_interior_registry()
    target = interior_id or registry["default_interior_id"]
    for interior in registry["interiors"]:
        if interior["id"] == target:
            return copy.deepcopy(interior)
    raise ShipInteriorError(f"unknown interior archetype: {target}")


def _room_index(interior: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {room["id"]: room for room in interior["rooms"]}


def _interaction_index() -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in load_interaction_registry()["interactions"]}


def validate_interior_archetype(interior_id: str | None = None) -> dict[str, Any]:
    interior = _interior(interior_id)
    rooms = _room_index(interior)
    failures: list[str] = []

    if interior["default_room_id"] not in rooms:
        failures.append("default room is missing")
    for room in rooms.values():
        for neighbor in room.get("adjacent_rooms", []):
            if neighbor not in rooms:
                failures.append(f"{room['id']} references missing room {neighbor}")
            elif room["id"] not in rooms[neighbor].get("adjacent_rooms", []):
                failures.append(f"room connection is not bidirectional: {room['id']} -> {neighbor}")
        for interaction_id in room.get("interaction_ids", []):
            interaction = _interaction_index().get(interaction_id)
            if interaction is None and interaction_id not in {
                "review_command_queue",
                "set_expedition_posture",
                "resolve_command_recall",
                "review_ship_directory",
                "crew_debrief",
                "informal_hypothesis_exchange",
                "record_crew_wellbeing_report",
                "review_planetary_case",
                "review_signal_case",
                "build_mission_strategy",
                "review_private_log",
                "rearrange_room_items",
                "design_personal_item",
                "review_collaborator_log",
            }:
                failures.append(f"unknown interaction: {interaction_id}")
            elif interaction is not None and room["id"] not in interaction["room_ids"]:
                failures.append(f"interaction {interaction_id} not allowed in {room['id']}")

    if rooms:
        visited = {interior["default_room_id"]}
        queue = deque(visited)
        while queue:
            current = queue.popleft()
            for neighbor in rooms[current].get("adjacent_rooms", []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        missing = sorted(set(rooms) - visited)
        if missing:
            failures.append(f"disconnected rooms: {missing}")

    result = {
        "schema": "axm.ship-interior-validation.v1",
        "interior_id": interior["id"],
        "interior_version": interior["version"],
        "room_count": len(rooms),
        "valid": not failures,
        "failures": failures,
    }
    result["validation_receipt"] = domain_hash(result, "AXM-SHIP-INTERIOR-VALIDATION-V1")
    return result


def shortest_room_path(
    start_room_id: str,
    target_room_id: str,
    interior_id: str | None = None,
) -> list[str]:
    interior = _interior(interior_id)
    rooms = _room_index(interior)
    if start_room_id not in rooms or target_room_id not in rooms:
        raise ShipInteriorError("unknown start or target room")
    queue: deque[list[str]] = deque([[start_room_id]])
    visited = {start_room_id}
    while queue:
        path = queue.popleft()
        if path[-1] == target_room_id:
            return path
        for neighbor in rooms[path[-1]]["adjacent_rooms"]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(path + [neighbor])
    raise ShipInteriorError("no room path exists")


def _edge_minutes(interior: dict[str, Any], a: str, b: str) -> int:
    table = interior.get("travel_time_minutes", {})
    return int(table.get(f"{a}|{b}", table.get(f"{b}|{a}", 1)))


def create_interior_state(
    seed: str,
    interior_id: str | None = None,
    continuity_policy_id: str | None = None,
) -> dict[str, Any]:
    interior = _interior(interior_id)
    continuity = load_continuity_registry()
    policy_id = continuity_policy_id or continuity["default_policy_id"]
    if policy_id not in {row["id"] for row in continuity["policies"]}:
        raise ShipInteriorError(f"unknown continuity policy: {policy_id}")
    state = {
        "schema": "axm.ship-interior-state.v1",
        "interior_id": interior["id"],
        "interior_version": interior["version"],
        "seed_receipt": hashlib.sha256(seed.encode("utf-8")).hexdigest(),
        "current_room_id": interior["default_room_id"],
        "continuity_policy_id": policy_id,
        "personal_clock_minutes": 0,
        "expedition_clock_minutes": 0,
        "crew_operation_ticks": 0,
        "routine_events_resolved": [],
        "advisories": [],
        "pending_command_recall": None,
        "room_visit_history": [],
        "interaction_history": [],
        "inventory": copy.deepcopy(load_item_policy()["starter_items"]),
        "room_item_placements": {
            "primary_quarters": [],
            "collaborator_quarters": [],
        },
        "resource_state": {
            "fabrication_material_kg": 30.0,
            "fabrication_energy_kwh": 120.0,
        },
    }
    _append_visit(state, interior["default_room_id"], 0, "initial")
    state["state_hash"] = state_hash(state)
    return state


def state_hash(state: dict[str, Any]) -> str:
    clean = copy.deepcopy(state)
    clean.pop("state_hash", None)
    return domain_hash(clean, "AXM-SHIP-INTERIOR-STATE-V1")


def _append_visit(state: dict[str, Any], room_id: str, travel_minutes: int, reason: str) -> None:
    previous = state["room_visit_history"][-1]["visit_hash"] if state["room_visit_history"] else None
    record = {
        "sequence": len(state["room_visit_history"]) + 1,
        "room_id": room_id,
        "personal_clock_minutes": state["personal_clock_minutes"],
        "expedition_clock_minutes": state["expedition_clock_minutes"],
        "travel_minutes": travel_minutes,
        "reason": reason,
        "previous_visit_hash": previous,
    }
    record["visit_hash"] = domain_hash(record, "AXM-ROOM-VISIT-V1")
    state["room_visit_history"].append(record)


def set_continuity_policy(state: dict[str, Any], policy_id: str) -> dict[str, Any]:
    policies = {row["id"]: row for row in load_continuity_registry()["policies"]}
    if policy_id not in policies:
        raise ShipInteriorError(f"unknown continuity policy: {policy_id}")
    updated = copy.deepcopy(state)
    updated["continuity_policy_id"] = policy_id
    updated["state_hash"] = state_hash(updated)
    return updated


def _deterministic_routine_event(state: dict[str, Any]) -> dict[str, Any]:
    tick = state["crew_operation_ticks"] + 1
    digest = hashlib.sha256(f"{state['seed_receipt']}|CREW-TICK|{tick}".encode("utf-8")).digest()
    choices = [
        ("passive_scan_update", "science", "Routine passive scan completed."),
        ("course_solution_check", "navigation", "Navigation solution rechecked."),
        ("power_balance_check", "engineering", "Power balance remained inside current limits."),
        ("communications_archive_sync", "communications", "Communications archive synchronized."),
        ("thermal_watch", "engineering", "Thermal watch completed without a command-level excursion."),
    ]
    event_type, station, summary = choices[digest[0] % len(choices)]
    event = {
        "sequence": tick,
        "event_type": event_type,
        "authority_level": "routine",
        "station": station,
        "summary": summary,
        "expedition_clock_minutes": state["expedition_clock_minutes"],
    }
    event["event_hash"] = domain_hash(event, "AXM-CREW-ROUTINE-EVENT-V1")
    return event


def advance_away_operations(
    state: dict[str, Any],
    minutes: int,
    situation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if minutes < 0:
        raise ShipInteriorError("minutes cannot be negative")
    updated = copy.deepcopy(state)
    updated["personal_clock_minutes"] += minutes
    away = updated["current_room_id"] != "command_deck"
    paused = updated["continuity_policy_id"] == "axm.continuity.pause-away.v1" and away

    if not paused:
        updated["expedition_clock_minutes"] += minutes
        ticks = minutes // 5
        for _ in range(ticks):
            event = _deterministic_routine_event(updated)
            updated["crew_operation_ticks"] += 1
            updated["routine_events_resolved"].append(event)

    if situation is not None and not paused:
        level = situation.get("authority_level")
        if level not in {"routine", "advisory", "command_required"}:
            raise ShipInteriorError("unknown situation authority level")
        event = {
            "situation_id": situation.get("situation_id", domain_hash(situation, "AXM-SITUATION-ID-V1")[:16]),
            "authority_level": level,
            "summary": str(situation.get("summary", "Unspecified situation")),
            "reversible": bool(situation.get("reversible", level != "command_required")),
            "generated_at_expedition_minute": updated["expedition_clock_minutes"],
        }
        if level == "routine":
            event["crew_resolution"] = "resolved_and_logged"
            event["event_hash"] = domain_hash(event, "AXM-AWAY-SITUATION-V1")
            updated["routine_events_resolved"].append(event)
        elif level == "advisory":
            event["crew_resolution"] = "reversible_work_continues"
            event["event_hash"] = domain_hash(event, "AXM-AWAY-SITUATION-V1")
            updated["advisories"].append(event)
        else:
            event["crew_resolution"] = "irreversible_branch_held"
            event["safe_posture"] = "lowest immediate risk reversible posture"
            event["recall_required"] = True
            event["event_hash"] = domain_hash(event, "AXM-COMMAND-RECALL-V1")
            updated["pending_command_recall"] = event

    updated["state_hash"] = state_hash(updated)
    return updated


def move_to_room(
    state: dict[str, Any],
    target_room_id: str,
    reason: str = "player_navigation",
) -> dict[str, Any]:
    interior = _interior(state["interior_id"])
    rooms = _room_index(interior)
    if target_room_id not in rooms:
        raise ShipInteriorError(f"unknown target room: {target_room_id}")
    path = shortest_room_path(state["current_room_id"], target_room_id, state["interior_id"])
    minutes = sum(_edge_minutes(interior, a, b) for a, b in zip(path, path[1:]))
    updated = advance_away_operations(state, minutes)
    updated["current_room_id"] = target_room_id
    _append_visit(updated, target_room_id, minutes, reason)
    updated["state_hash"] = state_hash(updated)
    return updated


def answer_command_recall(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("pending_command_recall") is None:
        raise ShipInteriorError("there is no pending command recall")
    updated = move_to_room(state, "command_deck", reason="command_recall")
    recall = copy.deepcopy(updated["pending_command_recall"])
    recall["answered_at_personal_minute"] = updated["personal_clock_minutes"]
    recall["status"] = "commander_present_decision_pending"
    updated["pending_command_recall"] = recall
    updated["state_hash"] = state_hash(updated)
    return updated


def resolve_command_recall(
    state: dict[str, Any],
    command_choice: str,
    reasoning_summary: str,
) -> dict[str, Any]:
    if state["current_room_id"] != "command_deck":
        raise ShipInteriorError("command recall may only be resolved on the command deck")
    if state.get("pending_command_recall") is None:
        raise ShipInteriorError("there is no pending command recall")
    updated = copy.deepcopy(state)
    recall = copy.deepcopy(updated["pending_command_recall"])
    recall["command_choice"] = command_choice
    recall["reasoning_summary"] = reasoning_summary
    recall["status"] = "resolved"
    recall["resolution_hash"] = domain_hash(recall, "AXM-COMMAND-RECALL-RESOLUTION-V1")
    updated["routine_events_resolved"].append(recall)
    updated["pending_command_recall"] = None
    updated["state_hash"] = state_hash(updated)
    return updated


def _require_room(state: dict[str, Any], interaction_id: str) -> dict[str, Any]:
    interaction = _interaction_index().get(interaction_id)
    if interaction is None:
        raise ShipInteriorError(f"interaction is not implemented by the factual engine: {interaction_id}")
    if state["current_room_id"] not in interaction["room_ids"]:
        raise ShipInteriorError(f"{interaction_id} is not available in {state['current_room_id']}")
    return interaction


def _positive(value: Any, name: str, allow_zero: bool = True) -> float:
    result = float(value)
    if result < 0 or (not allow_zero and result == 0):
        raise ShipInteriorError(f"{name} must be {'positive' if not allow_zero else 'non-negative'}")
    return result


def _record_interaction(
    state: dict[str, Any],
    interaction: dict[str, Any],
    inputs: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    updated = copy.deepcopy(state)
    previous = updated["interaction_history"][-1]["interaction_hash"] if updated["interaction_history"] else None
    record = {
        "sequence": len(updated["interaction_history"]) + 1,
        "room_id": updated["current_room_id"],
        "interaction_id": interaction["id"],
        "truth_class": interaction["truth_class"],
        "claim_limit": interaction["claim_limit"],
        "inputs": inputs,
        "result": result,
        "personal_clock_minutes": updated["personal_clock_minutes"],
        "expedition_clock_minutes": updated["expedition_clock_minutes"],
        "previous_interaction_hash": previous,
    }
    record["interaction_hash"] = domain_hash(record, "AXM-ROOM-INTERACTION-V1")
    updated["interaction_history"].append(record)
    updated["state_hash"] = state_hash(updated)
    return updated


def perform_room_interaction(
    state: dict[str, Any],
    interaction_id: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    interaction = _require_room(state, interaction_id)
    p = copy.deepcopy(parameters)

    if interaction_id == "review_consumable_duration":
        crew = _positive(p["crew_count"], "crew_count", allow_zero=False)
        food = _positive(p["food_kg"], "food_kg")
        water = _positive(p["water_liters"], "water_liters")
        food_rate = _positive(p["food_kg_per_person_day"], "food rate", allow_zero=False)
        water_rate = _positive(p["water_liters_per_person_day"], "water rate", allow_zero=False)
        food_days = food / (crew * food_rate)
        water_days = water / (crew * water_rate)
        result = {
            "food_days_remaining": round(food_days, 3),
            "water_days_remaining": round(water_days, 3),
            "limiting_consumable_days": round(min(food_days, water_days), 3),
            "limiting_consumable": "food" if food_days <= water_days else "water",
        }

    elif interaction_id == "inspect_power_balance":
        generation = _positive(p["generation_kw"], "generation_kw")
        base = _positive(p["base_load_kw"], "base_load_kw")
        active = _positive(p["active_load_kw"], "active_load_kw")
        reserve = _positive(p["reserve_requirement_kw"], "reserve_requirement_kw")
        gross = generation - base - active
        operational = gross - reserve
        result = {
            "gross_margin_kw": round(gross, 3),
            "operational_margin_kw": round(operational, 3),
            "power_state": "surplus" if operational >= 0 else "deficit",
        }

    elif interaction_id == "review_thermal_margin":
        waste = _positive(p["waste_heat_kw"], "waste_heat_kw")
        rejection = _positive(p["radiator_rejection_kw"], "radiator_rejection_kw")
        reserve = _positive(p["thermal_reserve_kw"], "thermal_reserve_kw")
        gross = rejection - waste
        operational = gross - reserve
        result = {
            "gross_thermal_margin_kw": round(gross, 3),
            "operational_thermal_margin_kw": round(operational, 3),
            "thermal_state": "within_margin" if operational >= 0 else "over_margin",
        }

    elif interaction_id == "estimate_repair_duration":
        work = _positive(p["estimated_work_hours"], "estimated_work_hours")
        crew = _positive(p["available_qualified_crew"], "available_qualified_crew", allow_zero=False)
        efficiency = min(1.0, max(0.05, float(p["parallel_efficiency"])))
        access = max(0.1, float(p["access_factor"]))
        elapsed = work / (crew * efficiency) * access
        result = {"estimated_elapsed_hours": round(elapsed, 3)}

    elif interaction_id == "calibrate_sensor":
        current = _positive(p["current_error_pct"], "current_error_pct")
        hours = _positive(p["calibration_hours"], "calibration_hours")
        quality = min(1.0, max(0.0, float(p["reference_quality"])))
        improvement_fraction = 1.0 - math.exp(-0.22 * hours * quality)
        after = max(0.02, current * (1.0 - 0.85 * improvement_fraction))
        result = {
            "estimated_error_pct_after": round(after, 5),
            "improvement_pct_points": round(current - after, 5),
        }

    elif interaction_id == "review_radiation_risk_index":
        environment = _positive(p["environment_index"], "environment_index")
        shielding = max(0.01, float(p["shielding_factor"]))
        exposure = _positive(p["exposure_hours"], "exposure_hours")
        tolerance = max(0.01, float(p["electronics_tolerance"]))
        risk = environment * exposure / (shielding * tolerance)
        result = {"relative_risk_index": round(risk, 5)}

    elif interaction_id == "compare_hypotheses":
        hypotheses = p.get("hypotheses")
        if not isinstance(hypotheses, list) or not hypotheses:
            raise ShipInteriorError("hypotheses must be a non-empty list")
        ranked = []
        unresolved = set()
        for row in hypotheses:
            supporting = int(row.get("supporting_channels", 0))
            independent = int(row.get("independent_replications", 0))
            controls = int(row.get("controls_passed", 0))
            contradictions = int(row.get("contradictions", 0))
            missing = list(row.get("unresolved_controls", []))
            score = supporting + 1.5 * independent + 0.75 * controls - 1.25 * contradictions
            ranked.append({
                "hypothesis_id": row["hypothesis_id"],
                "transparent_score": round(score, 3),
                "supporting_channels": supporting,
                "independent_replications": independent,
                "controls_passed": controls,
                "contradictions": contradictions,
            })
            unresolved.update(missing)
        ranked.sort(key=lambda row: (-row["transparent_score"], row["hypothesis_id"]))
        top = ranked[0]
        if top["independent_replications"] >= 2 and top["controls_passed"] >= 3:
            ceiling = "strong_candidate_not_proven"
        elif top["supporting_channels"] >= 2:
            ceiling = "replicated_anomaly"
        else:
            ceiling = "candidate_anomaly"
        result = {
            "ranked_hypotheses": ranked,
            "unresolved_controls": sorted(unresolved),
            "claim_ceiling": ceiling,
        }

    elif interaction_id == "design_control_test":
        alternatives = list(p.get("alternative_explanations", []))
        instruments = list(p.get("available_instruments", []))
        if not alternatives:
            raise ShipInteriorError("at least one alternative explanation is required")
        if not instruments:
            raise ShipInteriorError("at least one available instrument is required")
        plan = []
        for index, alternative in enumerate(alternatives):
            instrument = instruments[index % len(instruments)]
            plan.append({
                "alternative": alternative,
                "instrument": instrument,
                "goal": f"seek an observation that separates {p['target_hypothesis']} from {alternative}",
                "status": "planned_not_executed",
            })
        result = {
            "control_plan": plan,
            "blocked_claims": [
                "test success",
                "hypothesis confirmation",
                "alternative elimination",
            ],
        }

    elif interaction_id == "fabricate_room_item":
        material = _positive(p["material_kg"], "material_kg")
        energy = _positive(p["energy_kwh"], "energy_kwh")
        hours = _positive(p["fabrication_hours"], "fabrication_hours")
        available_material = float(state["resource_state"]["fabrication_material_kg"])
        available_energy = float(state["resource_state"]["fabrication_energy_kwh"])
        if material > available_material or energy > available_energy:
            raise ShipInteriorError("insufficient fabrication material or energy")
        validation = p.get("capability_validation")
        status = "validated_tool" if validation else "experimental" if p.get("intended_capability") else "decorative"
        item_core = {
            "display_name": str(p["item_name"]),
            "provenance_class": "fabricated",
            "status_class": status,
            "material_kg": material,
            "energy_kwh": energy,
            "fabrication_hours": hours,
            "intended_capability": p.get("intended_capability"),
            "capability_validation": validation,
            "created_at_expedition_minute": state["expedition_clock_minutes"],
        }
        item_core["origin_receipt"] = domain_hash(item_core, "AXM-FABRICATED-ITEM-V1")
        item_core["id"] = f"axm.item.fabricated.{item_core['origin_receipt'][:16]}"
        result = {
            "item_record": item_core,
            "remaining_material_kg": round(available_material - material, 5),
            "remaining_energy_kwh": round(available_energy - energy, 5),
        }

    elif interaction_id == "display_provenanced_item":
        item_id = str(p["item_id"])
        room_id = str(p["room_id"])
        if room_id != state["current_room_id"]:
            raise ShipInteriorError("item can only be placed in the current room")
        item = next((row for row in state["inventory"] if row["id"] == item_id), None)
        if item is None:
            raise ShipInteriorError("item is not in inventory")
        placement = {
            "item_id": item_id,
            "room_id": room_id,
            "display_anchor": str(p["display_anchor"]),
            "placed_at_expedition_minute": state["expedition_clock_minutes"],
            "item_status_class": item["status_class"],
        }
        placement["placement_receipt"] = domain_hash(placement, "AXM-ITEM-PLACEMENT-V1")
        result = {"placement": placement}

    elif interaction_id == "rest_cycle":
        duration = int(_positive(p["duration_minutes"], "duration_minutes"))
        result = {
            "personal_time_advanced": duration,
            "rest_log": "Rest period recorded. No unvalidated medical or performance effect applied.",
        }

    elif interaction_id == "offline_alternative_review":
        evidence = list(p.get("known_evidence", []))
        alternatives = list(p.get("known_alternatives", []))
        rows = []
        for alternative in alternatives:
            matched = sum(1 for item in evidence if alternative.lower() in str(item).lower())
            rows.append({
                "alternative": alternative,
                "explicit_evidence_mentions": matched,
                "status": "requires_test" if matched == 0 else "still_plausible",
            })
        result = {
            "case_id": p["case_id"],
            "alternative_review": rows,
            "external_ai_used": False,
            "new_evidence_created": False,
        }

    else:
        raise ShipInteriorError(f"interaction handler missing: {interaction_id}")

    updated = _record_interaction(state, interaction, p, result)

    if interaction_id == "fabricate_room_item":
        updated["inventory"].append(result["item_record"])
        updated["resource_state"]["fabrication_material_kg"] = result["remaining_material_kg"]
        updated["resource_state"]["fabrication_energy_kwh"] = result["remaining_energy_kwh"]
    elif interaction_id == "display_provenanced_item":
        room_id = p["room_id"]
        updated["room_item_placements"].setdefault(room_id, []).append(result["placement"])
    elif interaction_id == "rest_cycle":
        updated = advance_away_operations(updated, result["personal_time_advanced"])

    updated["state_hash"] = state_hash(updated)
    return updated


def verify_interior_state(state: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    validation = validate_interior_archetype(state.get("interior_id"))
    if not validation["valid"]:
        failures.extend(validation["failures"])

    expected_previous = None
    for index, visit in enumerate(state.get("room_visit_history", []), start=1):
        core = copy.deepcopy(visit)
        supplied = core.pop("visit_hash", None)
        if core.get("sequence") != index:
            failures.append(f"visit sequence mismatch at {index}")
        if core.get("previous_visit_hash") != expected_previous:
            failures.append(f"visit previous hash mismatch at {index}")
        expected = domain_hash(core, "AXM-ROOM-VISIT-V1")
        if supplied != expected:
            failures.append(f"visit hash mismatch at {index}")
        expected_previous = supplied

    expected_previous = None
    for index, record in enumerate(state.get("interaction_history", []), start=1):
        core = copy.deepcopy(record)
        supplied = core.pop("interaction_hash", None)
        if core.get("sequence") != index:
            failures.append(f"interaction sequence mismatch at {index}")
        if core.get("previous_interaction_hash") != expected_previous:
            failures.append(f"interaction previous hash mismatch at {index}")
        expected = domain_hash(core, "AXM-ROOM-INTERACTION-V1")
        if supplied != expected:
            failures.append(f"interaction hash mismatch at {index}")
        expected_previous = supplied

    supplied_state_hash = state.get("state_hash")
    if supplied_state_hash != state_hash(state):
        failures.append("state hash mismatch")

    result = {
        "schema": "axm.ship-interior-state-verification.v1",
        "valid": not failures,
        "failures": failures,
        "visits": len(state.get("room_visit_history", [])),
        "interactions": len(state.get("interaction_history", [])),
        "routine_events": len(state.get("routine_events_resolved", [])),
        "pending_command_recall": state.get("pending_command_recall") is not None,
    }
    result["verification_receipt"] = domain_hash(result, "AXM-SHIP-INTERIOR-VERIFY-V1")
    return result
