from __future__ import annotations

import copy
import hashlib
import re
from typing import Any

from .registry import data_path, load_json, load_source_registry

CONTACT_SCHEMA = "axm.long-horizon-contact-state.v1"
CONTACT_SNAPSHOT_SCHEMA = "axm.long-horizon-contact-snapshot.v1"


class ContactHorizonError(ValueError):
    """Raised when the long-horizon contact contract is violated."""


def load_contact_horizon_registry() -> dict[str, Any]:
    return load_json(data_path("contact_horizon_registry.json"))


def validate_contact_horizon_registry(registry: dict[str, Any] | None = None) -> list[str]:
    registry = registry or load_contact_horizon_registry()
    if int(registry.get("unlock_step", 0)) < 100000:
        raise ContactHorizonError("contact horizon may not unlock before step 100000")
    policy = registry.get("policy", {})
    required = [
        "unlock_is_eligibility_not_contact",
        "master_seed_does_not_preselect_alien_existence_or_intent",
        "contact_may_never_occur",
        "every_claim_climbs_an_evidence_ladder",
        "single_channel_detection_cannot_confirm_life_or_technology",
        "natural_and_instrumental_alternatives_are_tested_first",
        "no_species_is_assumed_benevolent_hostile_superior_or_inferior",
        "active_transmission_requires_explicit_governance",
    ]
    missing = [key for key in required if policy.get(key) is not True]
    if missing:
        raise ContactHorizonError(f"missing mandatory contact policies: {missing}")

    known_sources = set(load_source_registry().get("sources", {}))
    unknown = set(registry.get("source_ids", [])) - known_sources
    if unknown:
        raise ContactHorizonError(f"contact registry has unknown source IDs: {sorted(unknown)}")

    stages = registry.get("evidence_ladder", [])
    numbers = [int(item["stage"]) for item in stages]
    if numbers != list(range(len(numbers))):
        raise ContactHorizonError("contact evidence ladder stages must be continuous from zero")
    if not stages or stages[-1].get("id") != "interaction":
        raise ContactHorizonError("contact evidence ladder must end in an interaction stage")

    for item in registry.get("hypothesis_families", []):
        if not item.get("epistemic_class") or not item.get("not_allowed"):
            raise ContactHorizonError(f"hypothesis family lacks an epistemic boundary: {item.get('id')}")
    return []


def initial_contact_horizon_state() -> dict[str, Any]:
    registry = load_contact_horizon_registry()
    validate_contact_horizon_registry(registry)
    return {
        "schema": CONTACT_SCHEMA,
        "registry_version": registry["registry_version"],
        "unlock_step": int(registry["unlock_step"]),
        "phase": "dormant",
        "evidence_stage": 0,
        "evidence_stage_id": registry["evidence_ladder"][0]["id"],
        "candidate_id": None,
        "candidate_classes": [],
        "confirmed_external_life": False,
        "confirmed_external_technology": False,
        "confirmed_external_agency": False,
        "interaction_active": False,
        "active_transmission_authorized": False,
        "scientific_work": {
            "total_science_actions": 0,
            "independent_observation_context_ids": [],
            "cross_validations": 0,
            "false_positive_eliminations": 0,
            "passive_search_hours": 0.0,
            "dedicated_contact_searches": 0,
            "replicated_contact_anomalies": 0,
            "independent_contact_channels": [],
            "natural_alternatives_constrained": 0,
            "information_structure_tests": 0,
            "response_consistency_tests": 0,
        },
        "evidence_chain": [],
        "epistemic_contract": {
            "seed_scope": "No hidden alien species, intent, encounter, or contact date is selected by the master seed.",
            "unlock_scope": "Step 100000 opens a scientific search layer; it does not create an encounter.",
            "claim_scope": "Evidence stages cap what the simulator may say even when a dramatic interpretation is available.",
            "silence_scope": "A quiet search constrains only the searched signal class, sensitivity, direction, and time window.",
        },
    }


def _stage_item(registry: dict[str, Any], stage: int) -> dict[str, Any]:
    ladder = registry["evidence_ladder"]
    stage = min(max(0, int(stage)), len(ladder) - 1)
    return ladder[stage]


def _readiness(state: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    work = state["scientific_work"]
    req = registry["readiness_requirements"]
    contexts = len(set(work.get("independent_observation_context_ids", [])))
    checks = {
        "step_reached": int(state.get("current_step", 0)) >= int(registry["unlock_step"]),
        "science_actions": int(work["total_science_actions"]) >= int(req["minimum_total_science_actions"]),
        "independent_observation_contexts": contexts >= int(req["minimum_independent_observation_contexts"]),
        "cross_validations": int(work["cross_validations"]) >= int(req["minimum_cross_validations"]),
        "false_positive_eliminations": int(work["false_positive_eliminations"]) >= int(req["minimum_false_positive_eliminations"]),
        "passive_search_hours": float(work["passive_search_hours"]) >= float(req["minimum_passive_search_hours"]),
    }
    return {
        "checks": checks,
        "ready": all(checks.values()),
        "observation_context_count": contexts,
        "requirements": copy.deepcopy(req),
    }


def contact_horizon_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    registry = load_contact_horizon_registry()
    contact = copy.deepcopy(state.get("contact_horizon") or initial_contact_horizon_state())
    contact["current_step"] = int(state.get("turn", 0))
    readiness = _readiness(contact, registry)
    stage = _stage_item(registry, int(contact.get("evidence_stage", 0)))
    return {
        "schema": CONTACT_SNAPSHOT_SCHEMA,
        "current_step": int(state.get("turn", 0)),
        "unlock_step": int(registry["unlock_step"]),
        "steps_remaining": max(0, int(registry["unlock_step"]) - int(state.get("turn", 0))),
        "readiness": readiness,
        "phase": contact.get("phase", "dormant"),
        "evidence_stage": int(contact.get("evidence_stage", 0)),
        "evidence_stage_id": stage["id"],
        "evidence_stage_name": stage["name"],
        "claim_ceiling": stage["claim_ceiling"],
        "candidate_id": contact.get("candidate_id"),
        "candidate_classes": copy.deepcopy(contact.get("candidate_classes", [])),
        "confirmed_external_life": bool(contact.get("confirmed_external_life", False)),
        "confirmed_external_technology": bool(contact.get("confirmed_external_technology", False)),
        "confirmed_external_agency": bool(contact.get("confirmed_external_agency", False)),
        "interaction_active": bool(contact.get("interaction_active", False)),
        "honesty": (
            "The long-horizon layer describes search eligibility and evidence confidence. "
            "It does not assert that extraterrestrial life exists in this campaign."
        ),
    }


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:70] or "search"


def _contact_action(
    label: str,
    *,
    intent: str,
    priority: float,
    target_planet_id: str | None,
    focus: str,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    values = {"contact_horizon_focus": focus, **dict(parameters or {})}
    text = label.casefold()
    if any(word in text for word in ("wait", "listen", "passive", "baseline", "observe")):
        category = "patient_observation"
    elif any(word in text for word in ("repair", "calibrate", "audit")):
        category = "engineering"
    elif any(word in text for word in ("probe", "artifact", "local")):
        category = "probe"
    else:
        category = "instrument"
    return {
        "action_id": f"contact-horizon:{_slug(label)}",
        "label": label,
        "category": category,
        "source_thread": "contact-horizon",
        "target_planet_id": target_planet_id,
        "intent": intent,
        "priority": round(float(priority), 6),
        "parameters": values,
    }


def build_contact_actions(system: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    snapshot = contact_horizon_snapshot(state)
    if not snapshot["readiness"]["ready"]:
        return []

    target = None
    planets = system.get("planets", [])
    if planets:
        target = planets[int(state.get("turn", 0)) % len(planets)].get("id")
    stage = int(snapshot["evidence_stage"])
    actions: list[dict[str, Any]] = []

    if stage <= 1:
        actions.extend([
            _contact_action(
                "Run a blind multi-band technosignature survey",
                intent="Search without selecting a preferred alien technology template.",
                priority=1.08,
                target_planet_id=target,
                focus="blind-technosignature-survey",
                parameters={"integration_scale": 4.0, "simultaneous_channels": 3},
            ),
            _contact_action(
                "Audit archived anomalies against instrumental and natural false positives",
                intent="Increase evidential discipline before elevating any anomaly.",
                priority=1.06,
                target_planet_id=target,
                focus="false-positive-audit",
                parameters={"cross_calibration": True, "thermal_calibration": True},
            ),
            _contact_action(
                "Extend the passive listening baseline without transmitting",
                intent="Improve search coverage while preserving reversibility and avoiding an assumed contact narrative.",
                priority=1.02,
                target_planet_id=target,
                focus="passive-baseline",
                parameters={"integration_scale": 8.0},
            ),
        ])
    elif stage <= 3:
        actions.extend([
            _contact_action(
                "Repeat the candidate anomaly through an independent sensor chain",
                intent="Test replication without sharing the original processing path.",
                priority=1.12,
                target_planet_id=target,
                focus="independent-replication",
                parameters={"cross_calibration": True, "simultaneous_channels": 2},
            ),
            _contact_action(
                "Change geometry and search for a natural phase-dependent explanation",
                intent="Use orbital geometry to try to falsify the technological interpretation.",
                priority=1.10,
                target_planet_id=target,
                focus="natural-alternative-test",
                parameters={"phase_shift_deg": 71.0},
            ),
            _contact_action(
                "Run a blind reanalysis with the candidate label hidden",
                intent="Reduce confirmation bias and pipeline overfitting.",
                priority=1.04,
                target_planet_id=target,
                focus="blind-reanalysis",
                parameters={"band_isolation": True},
            ),
        ])
    elif stage <= 5:
        actions.extend([
            _contact_action(
                "Test the signal for compressible and error-correcting structure",
                intent="Check for information-bearing regularity without assuming language, mathematics, or intent.",
                priority=1.14,
                target_planet_id=target,
                focus="information-structure-test",
                parameters={"integration_scale": 5.0, "band_isolation": True},
            ),
            _contact_action(
                "Search nearby trajectories and stable orbits for a physical artifact",
                intent="Look for persistent technology rather than requiring a contemporaneous transmitter.",
                priority=1.08,
                target_planet_id=target,
                focus="artifact-search",
                parameters={"probe_profile": "artifact-recon"},
            ),
            _contact_action(
                "Maintain passive observation and wait for independent recurrence",
                intent="Prefer reversible evidence gathering over premature response.",
                priority=1.06,
                target_planet_id=target,
                focus="passive-recurrence-test",
                parameters={"integration_scale": 12.0},
            ),
        ])
    else:
        actions.extend([
            _contact_action(
                "Challenge the external-origin conclusion with a final adversarial review",
                intent="Search for unconceived alternatives before raising the claim ceiling.",
                priority=1.16,
                target_planet_id=target,
                focus="adversarial-review",
                parameters={"cross_calibration": True, "simultaneous_channels": 4},
            ),
            _contact_action(
                "Measure response consistency without increasing transmitted information",
                intent="Test agency while minimizing irreversible disclosure.",
                priority=1.10,
                target_planet_id=target,
                focus="response-consistency-test",
                parameters={"integration_scale": 6.0},
            ),
            _contact_action(
                "Convene a response-governance review and keep transmission disabled",
                intent="Separate evidence, ethics, safety, and authority before any active reply.",
                priority=1.08,
                target_planet_id=target,
                focus="governance-review",
                parameters={"archive_thread": False},
            ),
        ])
        contact = state.get("contact_horizon", {})
        if stage >= 8 and contact.get("active_transmission_authorized") is True:
            actions.append(_contact_action(
                "Transmit a minimal reversible calibration response",
                intent="Use only an explicitly authorized, low-information response designed for measurement rather than persuasion.",
                priority=0.96,
                target_planet_id=target,
                focus="authorized-minimal-response",
                parameters={"integration_scale": 2.0, "active_transmission": True},
            ))
    return actions


def _candidate_id(system_id: str, first_event_id: str) -> str:
    digest = hashlib.sha256(f"AXM-CONTACT-CANDIDATE-V1|{system_id}|{first_event_id}".encode("utf-8")).hexdigest()
    return f"candidate-{digest[:12]}"


def _append_evidence(contact: dict[str, Any], record: dict[str, Any]) -> None:
    contact.setdefault("evidence_chain", []).append(record)
    if len(contact["evidence_chain"]) > 512:
        contact["evidence_chain"] = contact["evidence_chain"][-512:]


def _derive_stage(contact: dict[str, Any], registry: dict[str, Any]) -> int:
    work = contact["scientific_work"]
    if contact.get("phase") == "dormant":
        return 0
    stage = 1
    dedicated = int(work["dedicated_contact_searches"])
    replicated = int(work["replicated_contact_anomalies"])
    channels = len(set(work["independent_contact_channels"]))
    constrained = int(work["natural_alternatives_constrained"])
    structure = int(work["information_structure_tests"])
    response = int(work["response_consistency_tests"])
    strong_records = sum(1 for item in contact.get("evidence_chain", []) if item.get("outcome_id") == "clear-evidence")

    if dedicated >= 1 and contact.get("candidate_id"):
        stage = 2
    if replicated >= 2 and channels >= 2:
        stage = 3
    if constrained >= 4 and int(work["false_positive_eliminations"]) >= 55:
        stage = 4
    if stage >= 4 and strong_records >= 5 and channels >= 3:
        stage = 5
    if stage >= 5 and structure >= 3:
        stage = 6
    if stage >= 6 and structure >= 6 and replicated >= 6 and channels >= 4:
        stage = 7
    if stage >= 7 and response >= 4:
        stage = 8
    if stage >= 8 and contact.get("interaction_active"):
        stage = 9
    return min(stage, len(registry["evidence_ladder"]) - 1)


def update_contact_horizon_after_event(
    system: dict[str, Any],
    state_before: dict[str, Any],
    state_after: dict[str, Any],
    *,
    event_id: str,
    action_record: dict[str, Any],
    outcome: dict[str, Any],
    physics: dict[str, Any],
) -> None:
    registry = load_contact_horizon_registry()
    contact = copy.deepcopy(state_before.get("contact_horizon") or initial_contact_horizon_state())
    contact["current_step"] = int(state_after.get("turn", 0))
    work = contact["scientific_work"]
    work["total_science_actions"] = int(work["total_science_actions"]) + 1
    target_id = action_record.get("target_planet_id") or physics.get("target_planet_id")
    phase = float(physics.get("orbital_state", {}).get("true_anomaly_deg", 0.0))
    context_id = f"{target_id or 'unknown-target'}:phase-{int(phase // 30) % 12:02d}"
    if context_id not in work["independent_observation_context_ids"]:
        work["independent_observation_context_ids"].append(context_id)
    duration = float(physics.get("expected_duration_hours", 0.0))
    category = action_record.get("category")
    if category in {"instrument", "patient_observation"}:
        work["passive_search_hours"] = round(float(work["passive_search_hours"]) + duration, 6)
    if action_record.get("parameters", {}).get("cross_calibration"):
        work["cross_validations"] = int(work["cross_validations"]) + 1
    if outcome.get("id") in {"ambiguous-evidence", "quiet-constraint"}:
        work["false_positive_eliminations"] = int(work["false_positive_eliminations"]) + 1

    readiness = _readiness(contact, registry)
    if readiness["ready"] and contact.get("phase") == "dormant":
        contact["phase"] = "search-eligible"
        _append_evidence(contact, {
            "event_id": event_id,
            "truth_type": "simulation_state",
            "kind": "horizon-unlock",
            "statement": "The long-horizon search became eligible after step and scientific-work gates were satisfied. No contact was generated.",
        })

    focus = action_record.get("parameters", {}).get("contact_horizon_focus")
    if focus and readiness["ready"]:
        work["dedicated_contact_searches"] = int(work["dedicated_contact_searches"]) + 1
        channel = str(physics.get("sensor", {}).get("wavelength_m", "unknown-channel"))
        if focus in {"independent-replication", "blind-technosignature-survey", "blind-reanalysis"}:
            channel = f"{focus}:{action_record.get('action_id')}"
            if channel not in work["independent_contact_channels"]:
                work["independent_contact_channels"].append(channel)
        if outcome.get("id") == "clear-evidence":
            work["replicated_contact_anomalies"] = int(work["replicated_contact_anomalies"]) + 1
            if contact.get("candidate_id") is None:
                contact["candidate_id"] = _candidate_id(system["system_id"], event_id)
                contact["candidate_classes"] = [
                    {"id": "instrument_or_pipeline_artifact", "status": "open"},
                    {"id": "abiotic_false_positive", "status": "open"},
                    {"id": "passive_technosignature", "status": "open"},
                    {"id": "unclassified_external_process", "status": "open"},
                ]
        if focus in {"false-positive-audit", "natural-alternative-test", "adversarial-review"}:
            increment = 2 if outcome.get("id") in {"clear-evidence", "quiet-constraint"} else 1
            work["natural_alternatives_constrained"] = int(work["natural_alternatives_constrained"]) + increment
            work["false_positive_eliminations"] = int(work["false_positive_eliminations"]) + increment
        if focus == "information-structure-test" and outcome.get("id") in {"clear-evidence", "unexpected-coupling"}:
            work["information_structure_tests"] = int(work["information_structure_tests"]) + 1
        if focus == "response-consistency-test" and outcome.get("id") == "clear-evidence":
            work["response_consistency_tests"] = int(work["response_consistency_tests"]) + 1
        _append_evidence(contact, {
            "event_id": event_id,
            "truth_type": "observation",
            "kind": focus,
            "outcome_id": outcome.get("id"),
            "statement": outcome.get("observation", {}).get("statement"),
            "claim_boundary": "This record may advance an evidence stage but cannot by itself confirm life, technology, intent, or agency.",
        })

    stage = _derive_stage(contact, registry)
    contact["evidence_stage"] = stage
    stage_item = _stage_item(registry, stage)
    contact["evidence_stage_id"] = stage_item["id"]
    contact["confirmed_external_technology"] = stage >= 7
    contact["confirmed_external_agency"] = stage >= 8
    # Life is deliberately separate: a technological artifact need not imply a living source.
    contact["confirmed_external_life"] = False
    state_after["contact_horizon"] = contact


def authorize_active_transmission(state: dict[str, Any], authorization_record: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(state)
    contact = updated.setdefault("contact_horizon", initial_contact_horizon_state())
    if int(contact.get("evidence_stage", 0)) < 8:
        raise ContactHorizonError("active transmission cannot be authorized before external agency is confirmed")
    if authorization_record.get("human_consent") is not True or authorization_record.get("ai_recommendation_recorded") is not True:
        raise ContactHorizonError("active transmission requires explicit human consent and a recorded AI recommendation")
    if authorization_record.get("reversibility_review") is not True or authorization_record.get("risk_review") is not True:
        raise ContactHorizonError("active transmission requires reversibility and risk review")
    contact["active_transmission_authorized"] = True
    contact["active_transmission_authorization"] = copy.deepcopy(authorization_record)
    return updated
