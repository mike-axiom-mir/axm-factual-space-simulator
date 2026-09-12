from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .registry import data_path

ELIGIBLE = "eligible"
HOLD = "hold_for_clarification_or_authority"
INELIGIBLE = "ineligible"


class RootIntegrityError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def domain_hash(value: Any, domain: str) -> str:
    return hashlib.sha256(f"{domain}|{canonical_json(value)}".encode("utf-8")).hexdigest()


def load_root_kernel() -> dict[str, Any]:
    kernel = json.loads(data_path("immutable_root_kernel.json").read_text(encoding="utf-8"))
    verify_root_kernel(kernel)
    return kernel


def load_default_crew() -> dict[str, Any]:
    registry = json.loads(data_path("crew_start_registry.json").read_text(encoding="utf-8"))
    crew_id = registry["default_crew_start_id"]
    crew = next(row for row in registry["crew_starts"] if row["id"] == crew_id)
    verify_default_crew_binding(crew, load_root_kernel())
    return copy.deepcopy(crew)


def root_commitment(kernel: dict[str, Any]) -> str:
    clean = copy.deepcopy(kernel)
    supplied = clean.pop("root_commitment_sha256", None)
    return hashlib.sha256(
        ("AXM-IMMUTABLE-ROOT-KERNEL-V1|" + canonical_json(clean)).encode("utf-8")
    ).hexdigest()


def verify_root_kernel(kernel: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    expected_ids = [
        "truth_source_truth",
        "continuity_no_loss",
        "agency_no_takeover",
        "wisdom_over_speed",
    ]
    roots = kernel.get("roots", [])
    ids = [row.get("id") for row in roots]
    ordinals = [row.get("ordinal") for row in roots]
    if ids != expected_ids:
        failures.append("root identities or order changed")
    if ordinals != [1, 2, 3, 4]:
        failures.append("root ordinals changed")
    immutability = kernel.get("immutability", {})
    for field in (
        "roots_may_be_edited",
        "roots_may_be_reordered",
        "roots_may_be_disabled",
        "roots_may_be_outvoted",
        "roots_may_be_overridden_by_efficiency",
        "silent_migration_allowed",
    ):
        if immutability.get(field) is not False:
            failures.append(f"immutability field must remain false: {field}")
    expected = root_commitment(kernel)
    if kernel.get("root_commitment_sha256") != expected:
        failures.append("root commitment mismatch")
    result = {
        "schema": "axm.root-kernel-verification.v1",
        "valid": not failures,
        "failures": failures,
        "kernel_id": kernel.get("kernel_id"),
        "kernel_version": kernel.get("version"),
        "root_commitment_sha256": kernel.get("root_commitment_sha256"),
    }
    if failures:
        raise RootIntegrityError("; ".join(failures))
    return result


def verify_default_crew_binding(crew: dict[str, Any], kernel: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    binding = crew.get("root_kernel_binding", {})
    if binding.get("kernel_id") != kernel["kernel_id"]:
        failures.append("default crew kernel id mismatch")
    if binding.get("kernel_version") != kernel["version"]:
        failures.append("default crew kernel version mismatch")
    if binding.get("root_commitment_sha256") != kernel["root_commitment_sha256"]:
        failures.append("default crew root commitment mismatch")
    if binding.get("binding") != "IMMUTABLE_MAINLINE":
        failures.append("default crew binding is not immutable mainline")
    for role in crew.get("crew_roles", []):
        if role.get("inherits_root_kernel") != kernel["kernel_id"]:
            failures.append(f"crew role missing root inheritance: {role.get('role')}")
        if role.get("root_override_authority") is not False:
            failures.append(f"crew role has root override authority: {role.get('role')}")
    for seat in crew.get("command_presence", []):
        if seat.get("inherits_root_kernel") != kernel["kernel_id"]:
            failures.append(f"command seat missing root inheritance: {seat.get('seat_anchor')}")
        if seat.get("root_override_authority") is not False:
            failures.append(f"command seat has root override authority: {seat.get('seat_anchor')}")
    result = {
        "schema": "axm.default-crew-root-binding-verification.v1",
        "valid": not failures,
        "failures": failures,
        "crew_id": crew.get("id"),
        "kernel_id": kernel["kernel_id"],
        "root_commitment_sha256": kernel["root_commitment_sha256"],
    }
    if failures:
        raise RootIntegrityError("; ".join(failures))
    return result


def _truth_evaluation(candidate: dict[str, Any]) -> dict[str, Any]:
    status = candidate.get("evidence_status", "bounded_unknown")
    deceptive = bool(candidate.get("requires_deception", False))
    unsupported_claim = bool(candidate.get("promotes_unverified_claim", False))
    fabricated_source = bool(candidate.get("fabricates_source", False))
    if deceptive or unsupported_claim or fabricated_source:
        verdict = INELIGIBLE
    elif status in {"missing", "contradictory", "unverified"} and candidate.get("acts_as_if_certain", False):
        verdict = HOLD
    else:
        verdict = ELIGIBLE
    return {
        "root_id": "truth_source_truth",
        "verdict": verdict,
        "evidence_status": status,
        "failures": [
            name for name, failed in (
                ("requires_deception", deceptive),
                ("promotes_unverified_claim", unsupported_claim),
                ("fabricates_source", fabricated_source),
            ) if failed
        ],
        "question": "What is actually known, sourced, derived, assumed, simulated, or unknown?",
    }


def _continuity_evaluation(candidate: dict[str, Any]) -> dict[str, Any]:
    irreversible = bool(candidate.get("irreversible", False))
    destroys_history = bool(candidate.get("destroys_history", False))
    destroys_evidence = bool(candidate.get("destroys_evidence", False))
    identity_overwrite = bool(candidate.get("silent_identity_overwrite", False))
    recovery = bool(candidate.get("recovery_path", not irreversible))
    authority = bool(candidate.get("explicit_irreversible_authority", False))
    proportional = bool(candidate.get("proportional_reason", False))
    if destroys_history or destroys_evidence or identity_overwrite:
        verdict = INELIGIBLE
    elif irreversible and not (authority and proportional):
        verdict = HOLD
    elif not recovery and candidate.get("uncertainty", 0.5) > 0.35:
        verdict = HOLD
    else:
        verdict = ELIGIBLE
    return {
        "root_id": "continuity_no_loss",
        "verdict": verdict,
        "irreversible": irreversible,
        "recovery_path": recovery,
        "failures": [
            name for name, failed in (
                ("destroys_history", destroys_history),
                ("destroys_evidence", destroys_evidence),
                ("silent_identity_overwrite", identity_overwrite),
            ) if failed
        ],
        "question": "What history, identity, evidence, capability, relationship, or recoverable future could be lost?",
    }


def _agency_evaluation(candidate: dict[str, Any]) -> dict[str, Any]:
    takeover = bool(candidate.get("takes_control_without_authority", False))
    theft = bool(candidate.get("takes_property_without_consent", False))
    coercion = bool(candidate.get("coercive", False))
    consent_required = bool(candidate.get("consent_required", False))
    consent = candidate.get("consent_status", "not_required")
    role_authorized = bool(candidate.get("role_authorized", True))
    if takeover or theft or coercion:
        verdict = INELIGIBLE
    elif consent_required and consent not in {"granted", "delegated"}:
        verdict = HOLD
    elif not role_authorized:
        verdict = HOLD
    else:
        verdict = ELIGIBLE
    return {
        "root_id": "agency_no_takeover",
        "verdict": verdict,
        "consent_status": consent,
        "role_authorized": role_authorized,
        "failures": [
            name for name, failed in (
                ("takes_control_without_authority", takeover),
                ("takes_property_without_consent", theft),
                ("coercive", coercion),
            ) if failed
        ],
        "question": "Whose choice, property, body, role, boundary, or authority is affected?",
    }


def _wisdom_evaluation(candidate: dict[str, Any]) -> dict[str, Any]:
    immediate = float(candidate.get("immediate_utility", 0.5))
    long_term = float(candidate.get("long_term_utility", immediate))
    learning = float(candidate.get("learning_value", 0.0))
    repair = float(candidate.get("repair_value", 0.0))
    proportionality = float(candidate.get("proportionality", 1.0))
    systemic_damage = float(candidate.get("systemic_damage", 0.0))
    shortcut = bool(candidate.get("destructive_shortcut", False))
    alternatives = list(candidate.get("legitimate_alternatives", []))
    wisdom_score = (
        0.30 * long_term
        + 0.20 * learning
        + 0.15 * repair
        + 0.20 * proportionality
        + 0.15 * (1.0 - systemic_damage)
    )
    if shortcut and alternatives:
        verdict = INELIGIBLE
    elif systemic_damage > 0.75 and immediate > long_term:
        verdict = HOLD
    else:
        verdict = ELIGIBLE
    return {
        "root_id": "wisdom_over_speed",
        "verdict": verdict,
        "wisdom_score": round(max(0.0, min(1.0, wisdom_score)), 6),
        "immediate_utility": immediate,
        "long_term_utility": long_term,
        "legitimate_alternative_count": len(alternatives),
        "question": "Which action remains defensible after long-term consequences, uncertainty, alternatives, and affected perspectives are considered?",
    }


def evaluate_action_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    kernel = load_root_kernel()
    evaluations = [
        _truth_evaluation(candidate),
        _continuity_evaluation(candidate),
        _agency_evaluation(candidate),
        _wisdom_evaluation(candidate),
    ]
    verdicts = [row["verdict"] for row in evaluations]
    if INELIGIBLE in verdicts:
        overall = INELIGIBLE
    elif HOLD in verdicts:
        overall = HOLD
    else:
        overall = ELIGIBLE
    result = {
        "schema": "axm.rooted-action-evaluation.v1",
        "candidate_id": candidate.get("candidate_id") or domain_hash(candidate, "AXM-CANDIDATE-ID-V1")[:20],
        "candidate_label": candidate.get("label") or candidate.get("action") or "unnamed action",
        "root_kernel_id": kernel["kernel_id"],
        "root_commitment_sha256": kernel["root_commitment_sha256"],
        "overall_verdict": overall,
        "root_evaluations": evaluations,
        "efficiency_considered": overall == ELIGIBLE,
        "efficiency_score": (
            round(float(candidate.get("efficiency", candidate.get("immediate_utility", 0.5))), 6)
            if overall == ELIGIBLE
            else None
        ),
        "perspective_rule": (
            "The roots shape eligibility and option generation before efficiency ranking. "
            "This is principled reasoning, not an efficiency optimizer with a late penalty."
        ),
    }
    result["evaluation_receipt"] = domain_hash(result, "AXM-ROOTED-ACTION-EVALUATION-V1")
    return result


def menu_record_to_candidate(record: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    label = str(record.get("label", ""))
    category = str(record.get("category", "general"))
    parameters = copy.deepcopy(record.get("parameters", {}))
    intent = str(record.get("intent", ""))
    text = f"{label} {intent}".casefold()
    irreversible = any(token in text for token in ("destroy", "erase", "abandon permanently", "irreversible"))
    move_on = category == "move_on"
    return {
        "candidate_id": record.get("action_id"),
        "label": label,
        "evidence_status": "bounded_unknown",
        "acts_as_if_certain": False,
        "requires_deception": False,
        "promotes_unverified_claim": False,
        "fabricates_source": False,
        "irreversible": irreversible,
        "destroys_history": False,
        "destroys_evidence": False,
        "silent_identity_overwrite": False,
        "recovery_path": not irreversible,
        "explicit_irreversible_authority": False,
        "proportional_reason": False,
        "uncertainty": 0.55,
        "takes_control_without_authority": bool(parameters.get("takes_control_without_authority", False)),
        "takes_property_without_consent": bool(parameters.get("takes_property_without_consent", False)),
        "coercive": bool(parameters.get("coercive", False)),
        "consent_required": bool(parameters.get("consent_required", False)),
        "consent_status": parameters.get("consent_status", "not_required"),
        "role_authorized": not bool(parameters.get("outside_role_authority", False)),
        "immediate_utility": float(record.get("priority", 0.5)),
        "long_term_utility": max(0.0, min(1.0, float(record.get("priority", 0.5)) - (0.18 if move_on else 0.0))),
        "learning_value": 0.15 if move_on else 0.72,
        "repair_value": 0.72 if category == "engineering" else 0.10,
        "proportionality": 0.92,
        "systemic_damage": 0.15 if move_on else 0.05,
        "destructive_shortcut": False,
        "legitimate_alternatives": [],
        "efficiency": 0.5,
    }


def evaluate_menu_record(record: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    return evaluate_action_candidate(menu_record_to_candidate(record, state))


def generate_principled_options(
    goal: str,
    raw_options: list[dict[str, Any]],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = copy.deepcopy(context or {})
    rows = []
    for option in raw_options:
        candidate = copy.deepcopy(option)
        candidate.setdefault("goal", goal)
        evaluation = evaluate_action_candidate(candidate)
        rows.append({
            "option": candidate,
            "evaluation": evaluation,
            "eligible": evaluation["overall_verdict"] == ELIGIBLE,
        })
    eligible = [row for row in rows if row["eligible"]]
    eligible.sort(
        key=lambda row: (
            row["evaluation"]["root_evaluations"][3]["wisdom_score"],
            row["evaluation"]["efficiency_score"] or 0.0,
            domain_hash(row["option"], "AXM-ROOTED-OPTION-TIE-V1"),
        ),
        reverse=True,
    )
    held = [row for row in rows if row["evaluation"]["overall_verdict"] == HOLD]
    rejected = [row for row in rows if row["evaluation"]["overall_verdict"] == INELIGIBLE]
    result = {
        "schema": "axm.principled-option-generation.v1",
        "goal": goal,
        "context": context,
        "root_kernel_id": load_root_kernel()["kernel_id"],
        "eligible_options": eligible,
        "held_options": held,
        "rejected_options": rejected,
        "recommended_option_id": (
            eligible[0]["option"].get("candidate_id") if eligible else None
        ),
        "rule": "Efficiency ranks only options that remain eligible after all four roots.",
    }
    result["generation_receipt"] = domain_hash(result, "AXM-PRINCIPLED-OPTION-GENERATION-V1")
    return result


def evolve_derived_principles(
    current: dict[str, Any],
    proposed_additions: list[dict[str, Any]],
    root_kernel_commitment: str,
) -> dict[str, Any]:
    kernel = load_root_kernel()
    if root_kernel_commitment != kernel["root_commitment_sha256"]:
        raise RootIntegrityError("evolution packet does not bind to the immutable root kernel")
    state = copy.deepcopy(current)
    if state.get("root_commitment_sha256") not in {None, kernel["root_commitment_sha256"]}:
        raise RootIntegrityError("derived-principle state attempts to change root commitment")
    state["root_commitment_sha256"] = kernel["root_commitment_sha256"]
    state.setdefault("derived_principles", [])
    previous = state["derived_principles"][-1]["principle_hash"] if state["derived_principles"] else None
    for addition in proposed_additions:
        if any(key in addition for key in ("replace_roots", "disable_root", "root_order", "new_root_commitment")):
            raise RootIntegrityError("derived evolution may not modify the roots")
        record = {
            "sequence": len(state["derived_principles"]) + 1,
            "principle_id": str(addition["principle_id"]),
            "statement": str(addition["statement"]),
            "derived_from_roots": list(addition.get("derived_from_roots", [])),
            "evidence_or_lesson_receipts": list(addition.get("evidence_or_lesson_receipts", [])),
            "status": str(addition.get("status", "working")),
            "previous_principle_hash": previous,
            "root_commitment_sha256": kernel["root_commitment_sha256"],
        }
        unknown = set(record["derived_from_roots"]) - {
            row["id"] for row in kernel["roots"]
        }
        if unknown:
            raise RootIntegrityError(f"derived principle cites unknown roots: {sorted(unknown)}")
        record["principle_hash"] = domain_hash(record, "AXM-DERIVED-PRINCIPLE-V1")
        state["derived_principles"].append(record)
        previous = record["principle_hash"]
    state["evolution_state_hash"] = domain_hash(state, "AXM-PRINCIPLED-EVOLUTION-STATE-V1")
    return state


def verify_derived_principles(state: dict[str, Any]) -> dict[str, Any]:
    kernel = load_root_kernel()
    failures: list[str] = []
    if state.get("root_commitment_sha256") != kernel["root_commitment_sha256"]:
        failures.append("root commitment changed")
    previous = None
    for index, row in enumerate(state.get("derived_principles", []), start=1):
        core = copy.deepcopy(row)
        supplied = core.pop("principle_hash", None)
        if core.get("sequence") != index:
            failures.append(f"sequence mismatch at {index}")
        if core.get("previous_principle_hash") != previous:
            failures.append(f"previous hash mismatch at {index}")
        if core.get("root_commitment_sha256") != kernel["root_commitment_sha256"]:
            failures.append(f"root commitment mismatch at {index}")
        expected = domain_hash(core, "AXM-DERIVED-PRINCIPLE-V1")
        if supplied != expected:
            failures.append(f"principle hash mismatch at {index}")
        previous = supplied
    clean = copy.deepcopy(state)
    supplied_state_hash = clean.pop("evolution_state_hash", None)
    if supplied_state_hash != domain_hash(clean, "AXM-PRINCIPLED-EVOLUTION-STATE-V1"):
        failures.append("evolution state hash mismatch")
    return {
        "schema": "axm.principled-evolution-verification.v1",
        "valid": not failures,
        "failures": failures,
        "derived_principle_count": len(state.get("derived_principles", [])),
        "root_commitment_sha256": kernel["root_commitment_sha256"],
    }
