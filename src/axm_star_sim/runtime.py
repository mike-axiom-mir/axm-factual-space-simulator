from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .contact_horizon import (
    contact_horizon_snapshot,
    initial_contact_horizon_state,
    update_contact_horizon_after_event,
)
from .entropy import EntropyPacket, resolve_entropy, roll
from .physics_runtime import (
    build_physics_snapshot,
    physics_open_threads,
    physics_resource_deltas,
    probability_modifiers,
    realized_measurement,
)
from .thread_engine import (
    action_by_input,
    build_action_menu,
    initial_threads,
    update_threads_after_event,
)

RUNTIME_SCHEMA = "axm.adventure-runtime.v4"
EVENT_SCHEMA = "axm.adventure-event.v4"


def canonical_hash(value: Any, domain: str = "AXM-RUNTIME-HASH-V1") -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(f"{domain}|{raw}".encode("utf-8")).hexdigest()


def _target_planet(system: dict[str, Any]) -> dict[str, Any]:
    trigger = system["adventure"]["selected_opportunity"].get("trigger", {})
    candidates = [trigger.get("planet_id"), trigger.get("rocky_id"), trigger.get("giant_id")]
    for planet_id in candidates:
        if planet_id:
            for planet in system["planets"]:
                if planet["id"] == planet_id:
                    return planet
    return system["planets"][0]


def _fact_value(value: Any, default: float) -> float:
    if isinstance(value, dict):
        value = value.get("value", default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def initial_runtime_state(system: dict[str, Any]) -> dict[str, Any]:
    ship = system["ship"]["systems"]
    active_mode = system.get("active_command_mode", "autonomous_deterministic")
    target = _target_planet(system)
    target_axis = _fact_value(target.get("facts", {}).get("semi_major_axis"), 1.0)
    state: dict[str, Any] = {
        "schema": RUNTIME_SCHEMA,
        "system_id": system["system_id"],
        "turn": 0,
        "mission_time_hours": 0.0,
        "resources": {
            "reactor_reserve_percent": float(ship["reactor_reserve_percent"]),
            "sensor_health_percent": float(ship["sensor_health_percent"]),
            "hull_integrity_percent": float(ship["hull_integrity_percent"]),
            "probe_count": int(ship["probe_count"]),
            "fuel_percent": 100.0,
            "heat_percent": 12.0,
            "knowledge_points": 0.0,
        },
        "navigation": {
            "ship_orbit_au": round(max(0.05, target_axis * 1.25), 9),
            "reference_frame": "star-centred two-body planning frame",
        },
        "active_probes": [],
        "threads": initial_threads(system),
        "open_threads": [system["adventure"]["selected_opportunity"]["id"]],
        "action_menu": None,
        "timeline": [],
        "last_event_hash": None,
        "command": {
            "active_mode": active_mode,
            "last_command_hash": None,
            "pending_session_id": None,
            "authority_contract": "Command authority is explicit per mode and is recorded in every resolved event.",
        },
        "contact_horizon": initial_contact_horizon_state(),
        "future_contract": {
            "seed_scope": "The master seed fixes the initial universe and stable generated facts, not every later event; it does not preselect extraterrestrial existence, intent, or a contact date.",
            "deferred_resolution": True,
            "physics_before_entropy": True,
            "dynamic_action_menus": True,
            "allowed_entropy_modes": [
                "deterministic",
                "local_live",
                "mixed_live",
                "external_beacon",
                "party_commit",
            ],
            "no_retcon": "Resolved events are hash-chained and replayable from their recorded entropy packet.",
        },
    }
    state["action_menu"] = build_action_menu(system, state)
    return state


def available_actions(system: dict[str, Any], state: dict[str, Any] | None = None) -> list[str]:
    if state is None:
        return list(system["adventure"]["selected_opportunity"]["actions"])
    menu = state.get("action_menu") or build_action_menu(system, state)
    return [str(item["label"]) for item in menu["actions"]]


def normalize_action(system: dict[str, Any], action: str, state: dict[str, Any] | None = None) -> str:
    if state is None:
        actions = available_actions(system)
        raw = action.strip()
        if raw.isdigit():
            index = int(raw) - 1
            if not 0 <= index < len(actions):
                raise ValueError(f"action index must be between 1 and {len(actions)}")
            return actions[index]
        for item in actions:
            if raw.casefold() == item.casefold():
                return item
        raise ValueError("action must be one of the generated opportunity actions or a 1-based action index")
    return str(action_by_input(system, state, action)["label"])


def _base_outcomes(opportunity: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": "clear-evidence",
            "title": "A repeatable result",
            "weight": 0.29,
            "knowledge": 12.0,
            "next_thread": "precision-follow-up",
        },
        {
            "id": "ambiguous-evidence",
            "title": "The uncertainty narrows, but survives",
            "weight": 0.30,
            "knowledge": 6.0,
            "sensor_delta": -1.0,
            "next_thread": "competing-hypotheses",
        },
        {
            "id": "unexpected-coupling",
            "title": "A second physical variable moves with the first",
            "weight": 0.16,
            "knowledge": 10.0,
            "heat_delta": 2.0,
            "next_thread": "cross-system-coupling",
        },
        {
            "id": "operational-complication",
            "title": "The ship pays for the attempt",
            "weight": 0.15,
            "knowledge": 3.0,
            "sensor_delta": -3.0,
            "hull_delta": -0.5,
            "next_thread": "repair-versus-discovery",
        },
        {
            "id": "quiet-constraint",
            "title": "Nothing rises above the current threshold",
            "weight": 0.10,
            "knowledge": 4.0,
            "next_thread": "detection-limit-review",
        },
    ]


def _adjust_outcomes(
    outcomes: list[dict[str, Any]],
    action_record: dict[str, Any],
    state: dict[str, Any],
    physics: dict[str, Any],
) -> list[dict[str, Any]]:
    adjusted = copy.deepcopy(outcomes)
    by_id = {item["id"]: item for item in adjusted}
    category = action_record["category"]
    resources = state["resources"]

    if category == "probe":
        by_id["clear-evidence"]["weight"] += 0.09
        by_id["operational-complication"]["weight"] += 0.08
        by_id["quiet-constraint"]["weight"] -= 0.04
    elif category == "patient_observation":
        by_id["clear-evidence"]["weight"] += 0.08
        by_id["ambiguous-evidence"]["weight"] += 0.04
        by_id["operational-complication"]["weight"] -= 0.06
    elif category == "instrument":
        by_id["ambiguous-evidence"]["weight"] += 0.05
        by_id["unexpected-coupling"]["weight"] += 0.06
    elif category == "engineering":
        by_id["operational-complication"]["weight"] -= 0.07
        by_id["quiet-constraint"]["weight"] += 0.04
    elif category == "move_on":
        by_id["quiet-constraint"]["weight"] += 0.22
        by_id["clear-evidence"]["weight"] -= 0.10
        by_id["unexpected-coupling"]["weight"] -= 0.04

    modifiers = probability_modifiers(physics)
    by_id["clear-evidence"]["weight"] += modifiers["clear_evidence"]
    by_id["ambiguous-evidence"]["weight"] += modifiers["ambiguous_evidence"]
    by_id["operational-complication"]["weight"] += modifiers["operational_complication"]
    by_id["quiet-constraint"]["weight"] += modifiers["quiet_constraint"]
    # Long delayed loops make a quiet/ambiguous result somewhat more likely because the
    # crew must act before every downstream response is available.
    by_id["ambiguous-evidence"]["weight"] += modifiers["delay_pressure"] * 0.6
    by_id["quiet-constraint"]["weight"] += modifiers["delay_pressure"] * 0.4

    if float(resources["sensor_health_percent"]) < 65:
        by_id["ambiguous-evidence"]["weight"] += 0.08
        by_id["clear-evidence"]["weight"] -= 0.06
    if float(resources["heat_percent"]) > 65:
        by_id["operational-complication"]["weight"] += 0.10
        by_id["clear-evidence"]["weight"] -= 0.05
    if int(resources["probe_count"]) <= 0 and category == "probe" and not action_record.get("parameters", {}).get("wait_for_probe"):
        raise ValueError("no probes remain for this action")

    for item in adjusted:
        item["weight"] = max(0.001, float(item["weight"]))
    total = sum(item["weight"] for item in adjusted)
    for item in adjusted:
        item["probability"] = item["weight"] / total
    return adjusted


def preview_turn(
    system: dict[str, Any],
    state: dict[str, Any] | None,
    action: str,
) -> dict[str, Any]:
    """Build the exact pre-entropy action, physics, and probability snapshot for a turn."""
    state_before = copy.deepcopy(state or initial_runtime_state(system))
    if not state_before.get("threads"):
        state_before["threads"] = initial_threads(system)
    if not state_before.get("action_menu"):
        state_before["action_menu"] = build_action_menu(system, state_before)
    action_record = action_by_input(system, state_before, action)
    opportunity = system["adventure"]["selected_opportunity"]
    physics = build_physics_snapshot(system, state_before, action_record)
    outcomes = _adjust_outcomes(_base_outcomes(opportunity), action_record, state_before, physics)
    return {
        "schema": "axm.turn-preview.v1",
        "turn": int(state_before["turn"]) + 1,
        "action_record": action_record,
        "physics_expectation": physics,
        "probability_snapshot": [
            {
                "id": item["id"],
                "title": item["title"],
                "probability": round(item["probability"], 8),
                "opened_thread": item["next_thread"],
            }
            for item in outcomes
        ],
        "physics_expectation_sha256": canonical_hash(physics, "AXM-PHYSICS-EXPECTATION-V1"),
        "action_menu_sha256": canonical_hash(state_before["action_menu"], "AXM-ACTION-MENU-V1"),
        "honesty": "This is the complete pre-entropy expectation. It contains no selected future outcome.",
    }


def _select_outcome(outcomes: list[dict[str, Any]], value: float) -> dict[str, Any]:
    cursor = 0.0
    for item in outcomes:
        cursor += item["probability"]
        if value <= cursor:
            return item
    return outcomes[-1]


def _merge_deltas(*parts: dict[str, float]) -> dict[str, float]:
    result: dict[str, float] = {}
    for part in parts:
        for key, value in part.items():
            result[key] = result.get(key, 0.0) + float(value)
    return {key: round(value, 6) for key, value in result.items()}


def _outcome_deltas(selected: dict[str, Any], physics: dict[str, Any], action_record: dict[str, Any]) -> dict[str, float]:
    outcome_specific: dict[str, float] = {"knowledge_points": float(selected.get("knowledge", 0.0))}
    if selected.get("sensor_delta"):
        outcome_specific["sensor_health_percent"] = float(selected["sensor_delta"])
    if selected.get("heat_delta"):
        outcome_specific["heat_percent"] = float(selected["heat_delta"])
    if selected.get("hull_delta"):
        outcome_specific["hull_integrity_percent"] = float(selected["hull_delta"])
    if selected["id"] == "operational-complication":
        thermal_ratio = float(physics["thermal"]["thermal_load_ratio"])
        radiation = float(physics["radiation"]["shielded_risk_index"])
        outcome_specific["heat_percent"] = outcome_specific.get("heat_percent", 0.0) + min(12.0, max(2.0, thermal_ratio * 3.0))
        outcome_specific["sensor_health_percent"] = outcome_specific.get("sensor_health_percent", 0.0) - min(4.0, radiation * 0.25)
    return _merge_deltas(physics_resource_deltas(physics, action_record), outcome_specific)


def _apply_deltas(state: dict[str, Any], deltas: dict[str, float]) -> dict[str, Any]:
    updated = copy.deepcopy(state)
    resources = updated["resources"]
    for key, delta in deltas.items():
        if key == "mission_time_hours":
            updated["mission_time_hours"] = round(updated["mission_time_hours"] + float(delta), 6)
        elif key in resources:
            resources[key] = round(resources[key] + float(delta), 6)
        else:
            raise ValueError(f"unknown runtime delta: {key}")

    for key in ("reactor_reserve_percent", "sensor_health_percent", "hull_integrity_percent", "fuel_percent", "heat_percent"):
        resources[key] = min(100.0, max(0.0, resources[key]))
    resources["probe_count"] = max(0, int(round(resources["probe_count"])))
    resources["knowledge_points"] = max(0.0, resources["knowledge_points"])
    return updated


def _physics_observation(
    selected: dict[str, Any],
    physics: dict[str, Any],
    measurement: dict[str, Any],
    opportunity: dict[str, Any],
) -> tuple[str, str]:
    snr = float(measurement["realized_snr"])
    expected = float(measurement["expected_snr"])
    phase = float(physics["orbital_state"]["true_anomaly_deg"])
    distance = float(physics["orbital_state"]["star_distance_au"])
    thermal = float(physics["thermal"]["thermal_load_ratio"])
    radiation = float(physics["radiation"]["shielded_risk_index"])
    one_way = float(physics["communications"]["one_way_light_time_s"])
    channel = measurement["detail_channel"]
    target = physics["target_planet_name"]

    if selected["id"] == "clear-evidence":
        observation = (
            f"At orbital phase {phase:.2f}° and {distance:.4f} AU from the star, the {channel} measurement of {target} "
            f"repeats with realized SNR {snr:.2f} (expected {expected:.2f})."
        )
        interpretation = (
            "The repeated channel now supports one causal explanation more strongly, but the simulator keeps the "
            "claim provisional until an independent geometry, instrument, or local measurement agrees."
        )
    elif selected["id"] == "ambiguous-evidence":
        observation = (
            f"The {channel} signal remains measurable at SNR {snr:.2f}, while photon/background/read-noise terms and "
            f"the current orbital phase still permit at least two explanations for '{opportunity['title']}'."
        )
        interpretation = "The evidence narrows the space of explanations without selecting a story answer that the measurements do not justify."
    elif selected["id"] == "unexpected-coupling":
        observation = (
            f"The {channel} changes alongside orbital phase {phase:.2f}°, thermal-load ratio {thermal:.3f}, or radiation-risk "
            f"index {radiation:.3f}; the correlation was not the original mission target."
        )
        interpretation = "A new cross-system causal thread is opened so later actions can test geometry, ship interference, and the local environment separately."
    elif selected["id"] == "operational-complication":
        observation = (
            f"The attempt reaches thermal-load ratio {thermal:.3f}, shielded radiation-risk index {radiation:.3f}, and a "
            f"{one_way:.1f}-second one-way command delay before measurement confidence stabilizes."
        )
        interpretation = "The opportunity remains open, but continued access now depends on explicit engineering, timing, and resource choices."
    else:
        observation = (
            f"No feature in the {channel} rises securely above the current detection threshold: realized SNR {snr:.2f} at "
            f"orbital phase {phase:.2f}° with sensor health and background noise recorded in the physics snapshot."
        )
        interpretation = "The non-detection constrains this geometry and instrument state; it is not evidence that the phenomenon is absent everywhere or always."
    return observation, interpretation


def _advance_probe_records(state: dict[str, Any]) -> None:
    now = float(state["mission_time_hours"])
    for probe in state.setdefault("active_probes", []):
        if probe.get("status") == "in-flight" and now >= float(probe["arrival_mission_time_hours"]):
            probe["status"] = "arrived-awaiting-telemetry"
            probe["arrived_mission_time_hours"] = round(now, 6)


def _record_probe_launch(
    state_before: dict[str, Any],
    state_after: dict[str, Any],
    action_record: dict[str, Any],
    physics: dict[str, Any],
    event_id: str,
) -> None:
    params = action_record.get("parameters", {})
    if action_record["category"] != "probe":
        return
    if any(params.get(key) for key in ("wait_for_probe", "trajectory_correction", "relay_mode")):
        return
    launch = float(state_before["mission_time_hours"])
    arrival = launch + float(physics["trajectory"]["transfer_time_days"]) * 24.0
    state_after.setdefault("active_probes", []).append({
        "probe_id": f"probe-{event_id.split(':')[-1]}",
        "source_event_id": event_id,
        "target_planet_id": physics["target_planet_id"],
        "target_planet_name": physics["target_planet_name"],
        "status": "in-flight",
        "launch_mission_time_hours": round(launch, 6),
        "arrival_mission_time_hours": round(arrival, 6),
        "trajectory": copy.deepcopy(physics["trajectory"]),
        "communications": copy.deepcopy(physics["communications"]),
    })


def resolve_turn(
    *,
    system: dict[str, Any],
    state: dict[str, Any] | None,
    action: str,
    entropy_mode: str,
    beacon: dict[str, Any] | None = None,
    party_reveals: list[dict[str, str]] | None = None,
    replay_entropy: dict[str, Any] | None = None,
    command_decision: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    state_before = copy.deepcopy(state or initial_runtime_state(system))
    if state_before["system_id"] != system["system_id"]:
        raise ValueError("runtime state belongs to a different star system")
    if not state_before.get("threads"):
        state_before["threads"] = initial_threads(system)
    if not state_before.get("action_menu"):
        state_before["action_menu"] = build_action_menu(system, state_before)

    preview = preview_turn(system, state_before, action)
    action_record = preview["action_record"]
    chosen_action = action_record["label"]
    if command_decision is None:
        command_decision = {
            "schema": "axm.command-decision.v1",
            "mode": state_before.get("command", {}).get("active_mode", "direct_runtime"),
            "status": "resolved",
            "authority": "direct_runtime",
            "selected_action": chosen_action,
            "selected_action_id": action_record["action_id"],
            "resolution_method": "direct_runtime_call",
            "proposals": [],
            "warnings": [],
        }
    else:
        command_decision = copy.deepcopy(command_decision)
    if command_decision.get("status") != "resolved":
        raise ValueError("command decision must be resolved before the event can evolve")
    decision_action = action_by_input(system, state_before, str(command_decision.get("selected_action", "")))
    if decision_action["action_id"] != action_record["action_id"]:
        raise ValueError("command decision selected_action does not match the action being executed")
    command_decision["selected_action"] = chosen_action
    command_decision["selected_action_id"] = action_record["action_id"]
    command_hash = command_decision.get("command_hash") or canonical_hash(command_decision, "AXM-COMMAND-HASH-V1")
    command_decision["command_hash"] = command_hash

    opportunity = system["adventure"]["selected_opportunity"]
    turn = int(state_before["turn"]) + 1
    event_id = f"{system['system_id']}:turn:{turn}"
    physics = preview["physics_expectation"]
    outcomes_by_id = {item["id"]: item for item in _adjust_outcomes(_base_outcomes(opportunity), action_record, state_before, physics)}
    outcomes = [outcomes_by_id[item["id"]] for item in preview["probability_snapshot"]]
    probability_snapshot = [
        {"id": item["id"], "probability": round(item["probability"], 8)} for item in outcomes
    ]
    context = {
        "system_id": system["system_id"],
        "generator_version": system["generator_version"],
        "event_id": event_id,
        "turn": turn,
        "opportunity_id": opportunity["id"],
        "action_id": action_record["action_id"],
        "action": chosen_action,
        "action_category": action_record["category"],
        "action_menu_sha256": canonical_hash(state_before["action_menu"], "AXM-ACTION-MENU-V1"),
        "physics_expectation_sha256": canonical_hash(physics, "AXM-PHYSICS-EXPECTATION-V1"),
        "state_before_sha256": canonical_hash(state_before),
        "outcome_probabilities": probability_snapshot,
        "previous_event_hash": state_before.get("last_event_hash"),
        "command_hash": command_hash,
        "command_mode": command_decision.get("mode"),
        "command_authority": command_decision.get("authority"),
    }
    entropy: EntropyPacket = resolve_entropy(
        mode=entropy_mode,
        master_seed=system["master_seed"],
        context=context,
        beacon=beacon,
        party_reveals=party_reveals,
        replay_packet=replay_entropy,
    )
    outcome_roll = roll(entropy, "outcome")
    noise_roll = roll(entropy, "sensor-noise")
    detail_roll = roll(entropy, "measurement-detail")
    selected = _select_outcome(outcomes, outcome_roll)
    measurement = realized_measurement(physics, noise_roll, detail_roll)
    observation, interpretation = _physics_observation(selected, physics, measurement, opportunity)
    deltas = _outcome_deltas(selected, physics, action_record)

    state_after = _apply_deltas(state_before, deltas)
    state_after["turn"] = turn
    _record_probe_launch(state_before, state_after, action_record, physics, event_id)
    _advance_probe_records(state_after)

    outcome_record = {
        "id": selected["id"],
        "title": selected["title"],
        "observation": {
            "truth_type": "observation",
            "statement": observation,
            "measurement": measurement,
            "notes": "This is an in-simulation measurement generated from the recorded physics expectation and entropy packet, not an external catalog fact.",
        },
        "interpretation": {
            "truth_type": "hypothesis",
            "statement": interpretation,
            "notes": "Interpretation remains revisable when later in-simulation evidence arrives.",
        },
        "resource_deltas": deltas,
        "opened_thread": selected["next_thread"],
    }
    contact_before = contact_horizon_snapshot(state_before)
    update_threads_after_event(
        system,
        state_after,
        event_id=event_id,
        turn=turn,
        action_record=action_record,
        outcome=outcome_record,
        additional_threads=physics_open_threads(physics, action_record),
    )
    update_contact_horizon_after_event(
        system,
        state_before,
        state_after,
        event_id=event_id,
        action_record=action_record,
        outcome=outcome_record,
        physics=physics,
    )
    # Thread expansion builds a menu before the long-horizon progress update.
    # Rebuild once so newly eligible evidence actions become visible immediately.
    state_after["action_menu"] = build_action_menu(system, state_after)
    contact_after = contact_horizon_snapshot(state_after)

    event: dict[str, Any] = {
        "schema": EVENT_SCHEMA,
        "event_id": event_id,
        "turn": turn,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "system_id": system["system_id"],
        "opportunity_id": opportunity["id"],
        "action": chosen_action,
        "action_id": action_record["action_id"],
        "action_category": action_record["category"],
        "action_record": action_record,
        "deferred_until_action": True,
        "predetermined_by_master_seed": entropy.predetermined_by_master_seed,
        "state_before_sha256": context["state_before_sha256"],
        "previous_event_hash": state_before.get("last_event_hash"),
        "probability_snapshot": probability_snapshot,
        "command": command_decision,
        "physics_expectation": physics,
        "entropy": entropy.to_dict(),
        "rolls": {
            "outcome": outcome_roll,
            "sensor_noise": noise_roll,
            "measurement_detail": detail_roll,
        },
        "outcome": outcome_record,
        "contact_horizon_before": contact_before,
        "contact_horizon_after": contact_after,
        "new_action_menu": copy.deepcopy(state_after["action_menu"]),
    }
    state_after.setdefault("command", {})["active_mode"] = command_decision.get("mode", state_before.get("command", {}).get("active_mode"))
    state_after["command"]["last_command_hash"] = command_hash
    state_after["command"]["pending_session_id"] = None
    state_after["timeline"].append({
        "event_id": event_id,
        "action": chosen_action,
        "action_id": action_record["action_id"],
        "outcome_id": selected["id"],
        "outcome_title": selected["title"],
        "entropy_mode": entropy_mode,
        "command_mode": command_decision.get("mode"),
        "command_authority": command_decision.get("authority"),
        "command_hash": command_hash,
        "target_planet_id": physics["target_planet_id"],
        "realized_snr": measurement["realized_snr"],
        "thermal_load_ratio": physics["thermal"]["thermal_load_ratio"],
        "radiation_risk_index": physics["radiation"]["shielded_risk_index"],
        "one_way_light_time_s": physics["communications"]["one_way_light_time_s"],
        "contact_evidence_stage": contact_after["evidence_stage"],
        "contact_phase": contact_after["phase"],
    })

    causal_base = copy.deepcopy(event)
    causal_base.pop("resolved_at", None)
    causal_base.get("entropy", {}).pop("created_at", None)
    event_hash = canonical_hash(causal_base, "AXM-EVENT-CHAIN-V3")
    event["event_hash"] = event_hash
    state_after["last_event_hash"] = event_hash
    event["state_after_sha256"] = canonical_hash(state_after)
    event["record_hash"] = canonical_hash(event, "AXM-EVENT-RECORD-V1")
    return event, state_after


def replay_event(system: dict[str, Any], state_before: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    replayed, _ = resolve_turn(
        system=system,
        state=state_before,
        action=event.get("action_id") or event["action"],
        entropy_mode=event["entropy"]["mode"],
        replay_entropy=event["entropy"],
        command_decision=event.get("command"),
    )
    return replayed


def verify_recorded_event(
    system: dict[str, Any], state_before: dict[str, Any], event: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        replayed, state_after = resolve_turn(
            system=system,
            state=state_before,
            action=event.get("action_id") or event["action"],
            entropy_mode=event["entropy"]["mode"],
            replay_entropy=event["entropy"],
            command_decision=event.get("command"),
        )
    except Exception as exc:
        return ({
            "event_id": event.get("event_id"),
            "recorded_event_hash_valid": False,
            "record_hash_valid": False,
            "outcome_matches": False,
            "rolls_match": False,
            "probabilities_match": False,
            "command_matches": False,
            "physics_matches": False,
            "action_menu_matches": False,
            "state_after_hash_matches": False,
            "replay_error": str(exc),
            "valid": False,
        }, copy.deepcopy(state_before))

    causal_base = copy.deepcopy(event)
    for key in ("resolved_at", "event_hash", "state_after_sha256", "record_hash"):
        causal_base.pop(key, None)
    causal_base.get("entropy", {}).pop("created_at", None)
    recorded_hash_valid = canonical_hash(causal_base, "AXM-EVENT-CHAIN-V3") == event.get("event_hash")
    record_base = {k: v for k, v in event.items() if k != "record_hash"}
    record_hash_valid = canonical_hash(record_base, "AXM-EVENT-RECORD-V1") == event.get("record_hash")
    outcome_matches = replayed["outcome"] == event["outcome"]
    rolls_match = replayed["rolls"] == event["rolls"]
    probabilities_match = replayed["probability_snapshot"] == event["probability_snapshot"]
    command_matches = replayed.get("command") == event.get("command")
    physics_matches = replayed.get("physics_expectation") == event.get("physics_expectation")
    action_menu_matches = replayed.get("new_action_menu") == event.get("new_action_menu")
    state_after["last_event_hash"] = event.get("event_hash")
    state_hash_matches = canonical_hash(state_after) == event.get("state_after_sha256")
    checks = {
        "event_id": event.get("event_id"),
        "recorded_event_hash_valid": recorded_hash_valid,
        "record_hash_valid": record_hash_valid,
        "outcome_matches": outcome_matches,
        "rolls_match": rolls_match,
        "probabilities_match": probabilities_match,
        "command_matches": command_matches,
        "physics_matches": physics_matches,
        "action_menu_matches": action_menu_matches,
        "state_after_hash_matches": state_hash_matches,
    }
    checks["valid"] = all(checks.values())
    return checks, state_after


def verify_ledger(system: dict[str, Any], events: list[dict[str, Any]]) -> tuple[bool, list[dict[str, Any]], dict[str, Any]]:
    state = initial_runtime_state(system)
    checks: list[dict[str, Any]] = []
    for event in events:
        result, state = verify_recorded_event(system, state, event)
        checks.append(result)
        if not result["valid"]:
            return False, checks, state
    return True, checks, state
