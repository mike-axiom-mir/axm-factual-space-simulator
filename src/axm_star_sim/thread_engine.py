from __future__ import annotations

import copy
import hashlib
import re
from typing import Any

from .contact_horizon import build_contact_actions

THREAD_SCHEMA = "axm.causal-thread.v1"
MENU_SCHEMA = "axm.dynamic-action-menu.v1"


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return text[:72] or "action"


def _hash_fraction(*parts: object) -> float:
    raw = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(f"AXM-ACTION-MENU-TIE-V1|{raw}".encode("utf-8")).hexdigest()
    return int(digest[:13], 16) / float(0x1FFFFFFFFFFFFF)


def _target_planet_id(system: dict[str, Any]) -> str:
    trigger = system["adventure"]["selected_opportunity"].get("trigger", {})
    for key in ("planet_id", "rocky_id", "giant_id"):
        if trigger.get(key):
            return str(trigger[key])
    return system["planets"][0]["id"]


def _category(label: str) -> str:
    text = label.casefold()
    if any(word in text for word in ("probe", "close pass", "deploy", "trajectory correction", "relay")):
        return "probe"
    if any(word in text for word in ("delay", "wait", "longer", "complete phase", "observe", "integration")):
        return "patient_observation"
    if any(word in text for word in ("spectroscopy", "sensor", "map", "orbit fitting", "geometry", "calibrat", "channel", "scan")):
        return "instrument"
    if any(word in text for word in ("repair", "cool", "radiator", "reroute", "shield")):
        return "engineering"
    if any(word in text for word in ("ignore", "continue", "direct route", "conserve", "depart", "archive")):
        return "move_on"
    return "general"


def make_thread(
    thread_id: str,
    *,
    title: str,
    kind: str,
    source_event_id: str | None,
    target_planet_id: str | None,
    evidence: list[dict[str, Any]] | None = None,
    parent_thread_id: str | None = None,
    status: str = "active",
    depth: int = 0,
) -> dict[str, Any]:
    return {
        "schema": THREAD_SCHEMA,
        "thread_id": thread_id,
        "title": title,
        "kind": kind,
        "status": status,
        "source_event_id": source_event_id,
        "parent_thread_id": parent_thread_id,
        "target_planet_id": target_planet_id,
        "depth": int(depth),
        "visits": 0,
        "evidence": list(evidence or []),
        "created_turn": 0,
        "updated_turn": 0,
    }


def initial_threads(system: dict[str, Any]) -> dict[str, dict[str, Any]]:
    opportunity = system["adventure"]["selected_opportunity"]
    target = _target_planet_id(system)
    thread = make_thread(
        opportunity["id"],
        title=opportunity["title"],
        kind="initial-opportunity",
        source_event_id=None,
        target_planet_id=target,
        evidence=[
            {
                "truth_type": "observation-plan",
                "statement": statement,
                "source": "generated-opportunity",
            }
            for statement in opportunity.get("observations", [])
        ],
    )
    return {thread["thread_id"]: thread}


def _action(
    *,
    label: str,
    source_thread: str,
    target_planet_id: str | None,
    intent: str,
    priority: float,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    category = _category(label)
    return {
        "action_id": f"{_slug(source_thread)}:{_slug(label)}",
        "label": label,
        "category": category,
        "source_thread": source_thread,
        "target_planet_id": target_planet_id,
        "intent": intent,
        "priority": round(float(priority), 6),
        "parameters": dict(parameters or {}),
    }


def _initial_actions(system: dict[str, Any], thread: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for index, label in enumerate(system["adventure"]["selected_opportunity"]["actions"]):
        result.append(_action(
            label=label,
            source_thread=thread["thread_id"],
            target_planet_id=thread.get("target_planet_id"),
            intent="Investigate the initial generated opportunity.",
            priority=1.0 - index * 0.03,
        ))
    return result


def _thread_actions(system: dict[str, Any], state: dict[str, Any], thread: dict[str, Any]) -> list[dict[str, Any]]:
    tid = thread["thread_id"]
    target = thread.get("target_planet_id") or _target_planet_id(system)
    visits = int(thread.get("visits", 0))
    kind = thread.get("kind", tid)
    common = {
        "source_thread": tid,
        "target_planet_id": target,
    }
    actions: list[dict[str, Any]] = []

    if kind in {"precision-follow-up", "clear-evidence"}:
        actions.extend([
            _action(label="Repeat the measurement with a longer integration window", intent="Test repeatability and improve photon statistics.", priority=0.96, parameters={"integration_scale": 2.5}, **common),
            _action(label="Cross-calibrate the signal against an independent sensor channel", intent="Separate target physics from instrument behaviour.", priority=0.94, parameters={"cross_calibration": True}, **common),
            _action(label="Revisit the target at a different orbital phase", intent="Test whether geometry controls the signal.", priority=0.90, parameters={"phase_shift_deg": 55.0}, **common),
        ])
    elif kind in {"competing-hypotheses", "ambiguous-evidence"}:
        actions.extend([
            _action(label="Isolate the strongest wavelength band and rescan", intent="Discriminate between competing spectral explanations.", priority=0.97, parameters={"band_isolation": True}, **common),
            _action(label="Change viewing geometry before repeating the observation", intent="Use phase and line-of-sight changes as a causal test.", priority=0.93, parameters={"phase_shift_deg": 35.0}, **common),
            _action(label="Deploy a probe to obtain a local measurement", intent="Replace remote inference with closer evidence.", priority=0.89, parameters={"probe_profile": "science-pass"}, **common),
        ])
    elif kind in {"cross-system-coupling", "unexpected-coupling"}:
        actions.extend([
            _action(label="Synchronize all relevant sensor channels for a coupled observation", intent="Measure whether the second variable tracks the first in time.", priority=0.98, parameters={"simultaneous_channels": 3}, **common),
            _action(label="Run an instrument thermal-interference calibration", intent="Test whether ship heat is creating the correlation.", priority=0.95, parameters={"thermal_calibration": True}, **common),
            _action(label="Compare the signal with the local radiation environment", intent="Test charged-particle interference as a causal explanation.", priority=0.92, parameters={"radiation_correlation": True}, **common),
        ])
    elif kind in {"repair-versus-discovery", "operational-complication"}:
        actions.extend([
            _action(label="Pause science operations and repair the stressed subsystem", intent="Restore measurement capability before further exposure.", priority=1.02, parameters={"repair_focus": "sensor"}, **common),
            _action(label="Reroute power through the radiator loop and continue at reduced output", intent="Trade observation speed for thermal margin.", priority=0.97, parameters={"power_fraction": 0.62}, **common),
            _action(label="Continue the observation with degraded instruments", intent="Accept lower confidence to preserve the current window.", priority=0.82, parameters={"degraded_operation": True}, **common),
        ])
    elif kind in {"detection-limit-review", "quiet-constraint"}:
        actions.extend([
            _action(label="Extend integration time to lower the detection threshold", intent="Improve signal-to-noise without claiming a guaranteed detection.", priority=0.96, parameters={"integration_scale": 4.0}, **common),
            _action(label="Observe from a more favourable orbital phase", intent="Increase target contrast using geometry.", priority=0.93, parameters={"phase_shift_deg": 80.0}, **common),
            _action(label="Archive the constrained non-detection and continue the mission", intent="Preserve the limit without spending more resources.", priority=0.84, parameters={"archive_thread": True}, **common),
        ])
    elif kind in {"probe-in-flight", "probe-trajectory"}:
        actions.extend([
            _action(label="Wait for the probe to reach its next telemetry window", intent="Advance the physical trajectory before expecting local data.", priority=0.98, parameters={"wait_for_probe": True}, **common),
            _action(label="Transmit a trajectory correction to the probe", intent="Trade fuel and communication delay for a better encounter geometry.", priority=0.94, parameters={"trajectory_correction": True}, **common),
            _action(label="Use the ship as a relay and prioritize probe telemetry", intent="Improve communication margin at the cost of ship bandwidth.", priority=0.91, parameters={"relay_mode": True}, **common),
        ])
    elif kind in {"communication-latency", "delayed-telemetry"}:
        actions.extend([
            _action(label="Hold course until the delayed telemetry response arrives", intent="Respect one-way light time instead of inventing immediate feedback.", priority=0.98, parameters={"wait_for_comm": True}, **common),
            _action(label="Send a store-and-forward command sequence", intent="Let the probe act locally during the communication gap.", priority=0.94, parameters={"autonomous_probe_sequence": True}, **common),
            _action(label="Reposition to improve the communication link geometry", intent="Trade travel time for a stronger link.", priority=0.88, parameters={"comm_geometry_change": True}, **common),
        ])
    elif kind in {"radiation-watch", "radiation-coupling"}:
        actions.extend([
            _action(label="Reduce exposed operations and shelter sensitive systems", intent="Lower radiation risk while preserving the mission.", priority=1.01, parameters={"shield_mode": True}, **common),
            _action(label="Measure the radiation field before resuming science", intent="Convert an environmental risk into evidence.", priority=0.97, parameters={"radiation_survey": True}, **common),
            _action(label="Continue through the radiation window with hardened systems", intent="Accept a declared risk for time-critical science.", priority=0.79, parameters={"hardened_run": True}, **common),
        ])
    elif kind in {"thermal-recovery", "thermal-load"}:
        actions.extend([
            _action(label="Rotate the ship to reduce absorbed stellar heating", intent="Change incidence geometry to improve thermal balance.", priority=1.00, parameters={"thermal_attitude": "edge-on"}, **common),
            _action(label="Enter a radiator cooldown period", intent="Delay the mission to recover thermal margin.", priority=0.98, parameters={"cooldown_hours": 8.0}, **common),
            _action(label="Continue at reduced instrument power", intent="Preserve the observation with lower heat and lower SNR.", priority=0.90, parameters={"power_fraction": 0.5}, **common),
        ])
    else:
        actions.extend([
            _action(label=f"Perform a focused follow-up on {thread['title']}", intent="Gather targeted evidence for the open causal thread.", priority=0.91, parameters={"focused_followup": True}, **common),
            _action(label="Change observation geometry and compare the result", intent="Use geometry as a causal discriminator.", priority=0.88, parameters={"phase_shift_deg": 45.0}, **common),
            _action(label="Archive this thread and return to mission priorities", intent="Close the investigation without inventing certainty.", priority=0.72, parameters={"archive_thread": True}, **common),
        ])

    for item in actions:
        item["priority"] = round(item["priority"] - min(0.18, visits * 0.035), 6)
    return actions


def _condition_actions(system: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    resources = state["resources"]
    target = _target_planet_id(system)
    result: list[dict[str, Any]] = []
    if float(resources["heat_percent"]) >= 68:
        result.append(_action(
            label="Enter a ship-wide thermal recovery cycle",
            source_thread="ship-condition:thermal",
            target_planet_id=target,
            intent="Prevent thermal load from silently becoming a generic failure roll.",
            priority=1.20,
            parameters={"cooldown_hours": 10.0},
        ))
    if float(resources["sensor_health_percent"]) <= 58:
        result.append(_action(
            label="Repair and recalibrate the primary sensor array",
            source_thread="ship-condition:sensors",
            target_planet_id=target,
            intent="Restore measurement reliability before interpreting weak signals.",
            priority=1.16,
            parameters={"repair_focus": "sensor"},
        ))
    if float(resources["reactor_reserve_percent"]) <= 35:
        result.append(_action(
            label="Conserve reactor power and suspend nonessential instruments",
            source_thread="ship-condition:power",
            target_planet_id=target,
            intent="Recover operating margin.",
            priority=1.13,
            parameters={"power_conservation": True},
        ))
    if int(resources.get("probe_count", 0)) <= 0:
        result.append(_action(
            label="Continue with remote sensing because no probes remain",
            source_thread="ship-condition:probe-scarcity",
            target_planet_id=target,
            intent="Respect the physical inventory instead of offering impossible probe actions.",
            priority=0.82,
            parameters={"remote_only": True},
        ))
    return result


def build_action_menu(system: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    threads = state.get("threads") or initial_threads(system)
    actions: list[dict[str, Any]] = []
    if int(state.get("turn", 0)) == 0:
        initial = threads[system["adventure"]["selected_opportunity"]["id"]]
        actions.extend(_initial_actions(system, initial))
    for thread in threads.values():
        if thread.get("status") == "active" and (int(state.get("turn", 0)) > 0 or thread.get("kind") != "initial-opportunity"):
            actions.extend(_thread_actions(system, state, thread))
    actions.extend(_condition_actions(system, state))
    actions.extend(build_contact_actions(system, state))

    # A long expedition may provisionally resolve or archive every investigation.
    # The bridge must then create an explicit mission-continuation choice rather
    # than return an empty menu or silently resurrect a resolved thread.
    if not actions:
        target = _target_planet_id(system)
        actions.extend([
            _action(
                label="Review resolved evidence and select the strongest remaining uncertainty",
                source_thread="mission-continuation:evidence-review",
                target_planet_id=target,
                intent="Create a new investigation from preserved limits and unresolved uncertainty.",
                priority=0.94,
                parameters={"mission_continuation": "evidence-review", "integration_scale": 1.4},
            ),
            _action(
                label="Survey a different planet for a new causal opportunity",
                source_thread="mission-continuation:system-survey",
                target_planet_id=target,
                intent="Move exploration to a different physical context without inventing a scripted event.",
                priority=0.91,
                parameters={"mission_continuation": "system-survey", "phase_shift_deg": 70.0},
            ),
            _action(
                label="Perform ship maintenance before opening the next investigation",
                source_thread="mission-continuation:maintenance",
                target_planet_id=target,
                intent="Convert a quiet interval into explicit engineering recovery.",
                priority=0.88,
                parameters={"mission_continuation": "maintenance", "repair_focus": "sensor"},
            ),
        ])

    # Remove actions that are physically unavailable and deduplicate labels.
    available: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in actions:
        if item["category"] == "probe" and int(state["resources"].get("probe_count", 0)) <= 0 and not item["parameters"].get("wait_for_probe"):
            continue
        key = item["label"].casefold()
        if key in seen:
            continue
        seen.add(key)
        item = copy.deepcopy(item)
        item["tie_value"] = _hash_fraction(system["master_seed"], state.get("turn", 0), item["action_id"])
        available.append(item)

    available.sort(key=lambda row: (row["priority"], row["tie_value"]), reverse=True)
    available = available[:9]
    for index, item in enumerate(available, start=1):
        item["index"] = index
        item.pop("tie_value", None)

    return {
        "schema": MENU_SCHEMA,
        "menu_version": int(state.get("turn", 0)) + 1,
        "generated_from_turn": int(state.get("turn", 0)),
        "active_thread_ids": [tid for tid, thread in threads.items() if thread.get("status") == "active"],
        "actions": available,
        "honesty": "Actions are generated from current causal threads, ship state, and—only after its gates—the long-horizon evidence layer. They are not a fixed dialogue tree and impossible inventory actions are removed.",
    }


def action_by_input(system: dict[str, Any], state: dict[str, Any], raw: str) -> dict[str, Any]:
    menu = state.get("action_menu") or build_action_menu(system, state)
    text = raw.strip()
    if text.isdigit():
        index = int(text)
        for item in menu["actions"]:
            if int(item["index"]) == index:
                return copy.deepcopy(item)
        raise ValueError(f"action index must be between 1 and {len(menu['actions'])}")
    for item in menu["actions"]:
        if text.casefold() in {item["label"].casefold(), item["action_id"].casefold()}:
            return copy.deepcopy(item)
    raise ValueError("action must match an action label, action_id, or 1-based menu index")


def update_threads_after_event(
    system: dict[str, Any],
    state_after: dict[str, Any],
    *,
    event_id: str,
    turn: int,
    action_record: dict[str, Any],
    outcome: dict[str, Any],
    additional_threads: list[dict[str, Any]] | None = None,
) -> None:
    threads = state_after.setdefault("threads", initial_threads(system))
    source_id = action_record.get("source_thread")
    if source_id in threads:
        source = threads[source_id]
        source["visits"] = int(source.get("visits", 0)) + 1
        source["updated_turn"] = turn
        source.setdefault("evidence", []).append({
            "event_id": event_id,
            "truth_type": "observation",
            "statement": outcome["observation"]["statement"],
            "outcome_id": outcome["id"],
        })
        if action_record.get("parameters", {}).get("archive_thread"):
            source["status"] = "archived"
        elif outcome["id"] == "clear-evidence" and source["visits"] >= 2:
            source["status"] = "resolved-provisional"

    descriptors: list[dict[str, Any]] = []
    opened = outcome.get("opened_thread")
    if opened:
        descriptors.append({
            "thread_id": opened,
            "title": opened.replace("-", " ").title(),
            "kind": opened,
            "target_planet_id": action_record.get("target_planet_id"),
        })
    descriptors.extend(additional_threads or [])

    parent_depth = int(threads.get(source_id, {}).get("depth", 0))
    for descriptor in descriptors:
        tid = str(descriptor["thread_id"])
        if tid in threads:
            threads[tid]["updated_turn"] = turn
            continue
        thread = make_thread(
            tid,
            title=str(descriptor.get("title") or tid.replace("-", " ").title()),
            kind=str(descriptor.get("kind") or tid),
            source_event_id=event_id,
            parent_thread_id=source_id,
            target_planet_id=descriptor.get("target_planet_id") or action_record.get("target_planet_id"),
            evidence=[{
                "event_id": event_id,
                "truth_type": "hypothesis",
                "statement": descriptor.get("reason", "Opened by the resolved event and remains investigable."),
            }],
            depth=parent_depth + 1,
        )
        thread["created_turn"] = turn
        thread["updated_turn"] = turn
        threads[tid] = thread

    state_after["open_threads"] = [tid for tid, thread in threads.items() if thread.get("status") == "active"]
    state_after["action_menu"] = build_action_menu(system, state_after)
