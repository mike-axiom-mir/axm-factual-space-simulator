from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from . import ship_blueprint as ship

RECOVERY_VERSION = "0.10.0-candidate"
RECOVERY_AUTHORITY_POLICY_ID = "axm.post-clearance-recovery-authority-policy.candidate.v1"

_BLOCKING_CRITICALITIES = {"crew_survival"}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any, domain: str) -> str:
    return hashlib.sha256(f"{domain}|{_canonical(value)}".encode("utf-8")).hexdigest()


def build_post_clearance_recovery_contract(clearance_contract: dict[str, Any]) -> dict[str, Any]:
    if clearance_contract.get("schema") != "axm.fault-clearance-apply-contract.v1":
        raise ValueError("unsupported fault clearance apply contract")
    upstream_ready = clearance_contract.get("status") == "ENGINE_AVAILABLE_REQUIRES_VERIFIED_CANDIDATE_AND_LIVE_SHIP_STATE"
    packet = {
        "schema": "axm.post-clearance-recovery-contract.v1",
        "version": RECOVERY_VERSION,
        "contract_id": f"post-clearance-recovery:{clearance_contract.get('source_failure_id')}:v1",
        "source_failure_id": clearance_contract.get("source_failure_id"),
        "source_system_id": clearance_contract.get("source_system_id"),
        "clearance_contract_id": clearance_contract.get("contract_id"),
        "clearance_contract_hash": clearance_contract.get("contract_hash"),
        "authority_policy_id": RECOVERY_AUTHORITY_POLICY_ID,
        "status": (
            "RECOVERY_ENGINE_AVAILABLE_AFTER_APPLIED_VERIFIED_CLEARANCE"
            if upstream_ready
            else "HOLD_UPSTREAM_CLEARANCE_CONTRACT"
        ),
        "required_inputs": [
            "authoritative_post_clearance_ship_state",
            "verified_clearance_apply_receipt",
            "recovery_evidence_ids",
            "independent_recovery_check_ids",
            "mission_commander_safe_state_exit_authorization",
        ],
        "recovery_semantics": "assess_residual_state_then_explicitly_authorize_safe_state_exit",
        "candidate_authority_policy": {
            "safe_state_exit": "mission_commander authorization required",
            "truth_status": "simulation_policy_candidate_not_canon",
        },
        "may_assume_full_recovery_from_fault_clearance": False,
        "may_restore_resources": False,
        "may_restore_system_health": False,
        "may_remove_load_sheds": False,
        "may_clear_other_faults": False,
        "may_exit_safe_state_automatically": False,
        "renderer_may_apply_recovery": False,
    }
    packet["contract_hash"] = _hash(packet, "AXM-POST-CLEARANCE-RECOVERY-CONTRACT-V1")
    return packet


def build_post_clearance_recovery_contract_catalog(
    clearance_catalog: dict[str, Any],
) -> dict[str, Any]:
    if clearance_catalog.get("schema") != "axm.fault-clearance-apply-contract-catalog.v1":
        raise ValueError("unsupported fault clearance apply contract catalog")
    rows = [
        build_post_clearance_recovery_contract(row)
        for row in clearance_catalog.get("contracts", [])
        if isinstance(row, dict)
    ]
    packet = {
        "schema": "axm.post-clearance-recovery-contract-catalog.v1",
        "version": RECOVERY_VERSION,
        "contract_count": len(rows),
        "contracts": rows,
        "authority": "contract_and_engine_availability_only",
        "safe_state_exited": False,
        "may_modify_presentation_runtime": False,
        "may_restore_resources": False,
    }
    packet["catalog_hash"] = _hash(packet, "AXM-POST-CLEARANCE-RECOVERY-CONTRACT-CATALOG-V1")
    return packet


def _validate_clearance_apply_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("schema") != "axm.fault-clearance-apply-receipt.v1":
        raise ValueError("unsupported fault clearance apply receipt")
    raw = copy.deepcopy(receipt)
    claimed = raw.pop("apply_receipt_hash", None)
    if claimed != _hash(raw, "AXM-FAULT-CLEARANCE-APPLY-RECEIPT-V1"):
        raise ValueError("fault clearance apply receipt hash mismatch")
    if receipt.get("status") != "APPLIED_VERIFIED_FAULT_CLEARANCE":
        raise ValueError("fault clearance apply receipt is not applied")
    if receipt.get("fault_cleared") is not True or receipt.get("repair_verified") is not True:
        raise ValueError("fault clearance apply receipt lacks verified clearance")
    if receipt.get("safe_state_exit_automatic") is not False:
        raise ValueError("clearance receipt violates explicit safe-state exit boundary")


def _failure_index() -> dict[str, dict[str, Any]]:
    registry = ship.load_failure_registry()
    return {
        str(row["id"]): row
        for row in registry.get("failure_modes", [])
        if isinstance(row, dict) and row.get("id")
    }


def _active_fault_rows(
    state: dict[str, Any],
    failures: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for system_id, health in sorted(state.get("system_health", {}).items()):
        if not isinstance(health, dict):
            continue
        for failure_id in sorted({str(v) for v in health.get("active_fault_ids", []) if v}):
            definition = failures.get(failure_id)
            rows.append({
                "failure_mode_id": failure_id,
                "system_id": system_id,
                "criticality": definition.get("criticality") if definition else "unknown",
                "command_level": definition.get("command_level") if definition else "unknown",
                "registry_known": definition is not None,
            })
    return rows


def _residual_state_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    systems = []
    for system_id, row in sorted(state.get("system_health", {}).items()):
        if not isinstance(row, dict):
            continue
        non_nominal = (
            float(row.get("health", 1.0)) < 1.0
            or float(row.get("availability", 1.0)) < 1.0
            or row.get("mode") != "nominal"
            or bool(row.get("active_fault_ids"))
        )
        if non_nominal:
            systems.append({
                "system_id": system_id,
                "health": row.get("health"),
                "availability": row.get("availability"),
                "mode": row.get("mode"),
                "active_fault_ids": sorted({str(v) for v in row.get("active_fault_ids", []) if v}),
            })

    structure = state.get("structure", {})
    atmosphere = state.get("atmosphere", {})
    water = state.get("water", {})
    communications = state.get("communications", {})
    navigation = state.get("navigation", {})
    radiation = state.get("radiation", {})
    command = state.get("command", {})
    residual_indicators: list[str] = []

    if systems:
        residual_indicators.append("non_nominal_system_state")
    if float(structure.get("health", 1.0)) < 1.0:
        residual_indicators.append("structure_health_below_one")
    if structure.get("pressure_boundary_state") != "nominal":
        residual_indicators.append("pressure_boundary_non_nominal")
    if structure.get("isolated_rooms"):
        residual_indicators.append("isolated_rooms_remain")
    if float(atmosphere.get("pressure_leak_kpa_per_hour", 0.0)) > 0.0:
        residual_indicators.append("pressure_leak_remains")
    if float(atmosphere.get("co2_removal_multiplier", 1.0)) < 1.0:
        residual_indicators.append("co2_removal_degraded")
    if float(atmosphere.get("oxygen_generation_multiplier", 1.0)) < 1.0:
        residual_indicators.append("oxygen_generation_degraded")
    if float(water.get("recovery_multiplier", 1.0)) < 1.0:
        residual_indicators.append("water_recovery_degraded")
    if water.get("quality_state") != "nominal":
        residual_indicators.append("water_quality_non_nominal")
    if float(communications.get("availability", 1.0)) < 1.0:
        residual_indicators.append("communications_degraded")
    if float(communications.get("telemetry_visibility_fraction", 1.0)) < 1.0:
        residual_indicators.append("telemetry_visibility_degraded")
    if float(navigation.get("pointing_performance_multiplier", 1.0)) < 1.0:
        residual_indicators.append("pointing_performance_degraded")
    if navigation.get("propulsion_available") is False:
        residual_indicators.append("propulsion_unavailable")
    if state.get("power", {}).get("shed_loads"):
        residual_indicators.append("load_sheds_remain")
    if radiation.get("shelter_active") is True:
        residual_indicators.append("radiation_shelter_active")
    if command.get("held_irreversible_actions"):
        residual_indicators.append("irreversible_action_holds_remain")

    return {
        "mode": state.get("mode"),
        "system_residuals": systems,
        "structure": {
            "health": structure.get("health"),
            "pressure_boundary_state": structure.get("pressure_boundary_state"),
            "isolated_rooms": copy.deepcopy(structure.get("isolated_rooms", [])),
        },
        "power": {
            "battery_energy_kwh": state.get("power", {}).get("battery_energy_kwh"),
            "battery_capacity_kwh": state.get("power", {}).get("battery_capacity_kwh"),
            "shed_loads": copy.deepcopy(state.get("power", {}).get("shed_loads", [])),
        },
        "atmosphere": {
            "cabin_pressure_kpa": atmosphere.get("cabin_pressure_kpa"),
            "pressure_leak_kpa_per_hour": atmosphere.get("pressure_leak_kpa_per_hour"),
            "oxygen_store_person_days": atmosphere.get("oxygen_store_person_days"),
            "co2_removal_multiplier": atmosphere.get("co2_removal_multiplier"),
            "oxygen_generation_multiplier": atmosphere.get("oxygen_generation_multiplier"),
        },
        "water": {
            "stored_potable_water_kg": water.get("stored_potable_water_kg"),
            "recovery_multiplier": water.get("recovery_multiplier"),
            "quality_state": water.get("quality_state"),
        },
        "crew": copy.deepcopy(state.get("crew", {})),
        "communications": {
            "availability": communications.get("availability"),
            "telemetry_visibility_fraction": communications.get("telemetry_visibility_fraction"),
        },
        "navigation": {
            "navigation_uncertainty_km": navigation.get("navigation_uncertainty_km"),
            "pointing_performance_multiplier": navigation.get("pointing_performance_multiplier"),
            "propulsion_available": navigation.get("propulsion_available"),
        },
        "radiation": {
            "environment_index": radiation.get("environment_index"),
            "cumulative_relative_exposure": radiation.get("cumulative_relative_exposure"),
            "shelter_active": radiation.get("shelter_active"),
        },
        "command": {
            "pending_recall": copy.deepcopy(command.get("pending_recall")),
            "held_irreversible_actions": copy.deepcopy(command.get("held_irreversible_actions", [])),
        },
        "residual_indicators": sorted(set(residual_indicators)),
    }


def _validate_clearance_provenance(
    state: dict[str, Any],
    clearance_receipt: dict[str, Any],
) -> None:
    failure_id = str(clearance_receipt.get("failure_mode_id") or "")
    system_id = str(clearance_receipt.get("system_id") or "")
    candidate_hash = clearance_receipt.get("candidate_hash")
    if not failure_id or not system_id or not candidate_hash:
        raise ValueError("clearance receipt identity is incomplete")
    health = state.get("system_health", {}).get(system_id)
    if not isinstance(health, dict):
        raise ValueError("cleared system is missing from authoritative ship state")
    if failure_id in health.get("active_fault_ids", []):
        raise ValueError("cleared fault is active again; recovery requires a new fault lifecycle")
    matching = [
        row for row in state.get("fault_ledger", [])
        if isinstance(row, dict)
        and row.get("record_type") == "verified_clearance"
        and row.get("failure_mode_id") == failure_id
        and row.get("system_id") == system_id
        and row.get("candidate_hash") == candidate_hash
        and row.get("fault_cleared") is True
        and row.get("repair_verified") is True
    ]
    if not matching:
        raise ValueError("authoritative ship state does not contain the pinned verified clearance")


def build_recovery_assessment(
    ship_state: dict[str, Any],
    clearance_apply_receipt: dict[str, Any],
    *,
    source_ref: str,
    evidence_ids: list[str],
    independent_check_ids: list[str],
) -> dict[str, Any]:
    if ship.verify_ship_state(ship_state).get("valid") is not True:
        raise ValueError("recovery assessment requires a valid authoritative ship state")
    _validate_clearance_apply_receipt(clearance_apply_receipt)
    _validate_clearance_provenance(ship_state, clearance_apply_receipt)

    source = str(source_ref or "").strip()
    evidence = sorted({str(v) for v in evidence_ids if str(v).strip()})
    independent = sorted({str(v) for v in independent_check_ids if str(v).strip()})
    failures = _failure_index()
    active_faults = _active_fault_rows(ship_state, failures)
    blocking_faults = [
        row for row in active_faults
        if not row["registry_known"]
        or row.get("criticality") in _BLOCKING_CRITICALITIES
        or row.get("command_level") == "command_required"
    ]
    evaluation = ship.evaluate_ship(ship_state)
    snapshot = _residual_state_snapshot(ship_state)
    blockers: list[str] = []

    if ship_state.get("mode") != "safe_state":
        blockers.append("ship_not_in_safe_state")
    if evaluation.get("crew_survival_state_currently_supported") is not True:
        blockers.append("crew_survival_state_not_currently_supported")
    if blocking_faults:
        blockers.append("blocking_active_faults_remain")
    command = ship_state.get("command", {})
    if command.get("pending_recall") is not None:
        blockers.append("command_recall_remains")
    if command.get("held_irreversible_actions"):
        blockers.append("irreversible_action_holds_remain")
    if not source:
        blockers.append("recovery_source_ref_missing")
    if not evidence:
        blockers.append("recovery_evidence_missing")
    if not independent:
        blockers.append("independent_recovery_check_missing")

    eligible = not blockers
    if ship_state.get("mode") != "safe_state":
        status = "RECOVERY_NO_SAFE_STATE_EXIT_REQUIRED"
    elif not eligible:
        status = "FAULT_CLEARED_RECOVERY_INCOMPLETE"
    elif snapshot["residual_indicators"]:
        status = "DEGRADED_SAFE_RECOVERY_RELEASE_ELIGIBLE"
    else:
        status = "NOMINAL_RECOVERY_RELEASE_ELIGIBLE"

    packet = {
        "schema": "axm.post-clearance-recovery-assessment.v1",
        "version": RECOVERY_VERSION,
        "assessment_id": _hash({
            "clearance_apply_receipt_hash": clearance_apply_receipt.get("apply_receipt_hash"),
            "state_hash": ship_state.get("state_hash"),
            "source_ref": source,
            "evidence_ids": evidence,
            "independent_check_ids": independent,
        }, "AXM-POST-CLEARANCE-RECOVERY-ASSESSMENT-ID-V1"),
        "source_failure_id": clearance_apply_receipt.get("failure_mode_id"),
        "source_system_id": clearance_apply_receipt.get("system_id"),
        "clearance_apply_receipt_hash": clearance_apply_receipt.get("apply_receipt_hash"),
        "clearance_state_hash_after": clearance_apply_receipt.get("state_hash_after"),
        "state_hash_assessed": ship_state.get("state_hash"),
        "source_ref": source,
        "evidence_ids": evidence,
        "independent_check_ids": independent,
        "crew_survival_state_currently_supported": evaluation.get("crew_survival_state_currently_supported"),
        "evaluation_receipt": evaluation.get("evaluation_receipt"),
        "active_faults": active_faults,
        "blocking_active_faults": blocking_faults,
        "residual_state_snapshot": snapshot,
        "release_blockers": sorted(set(blockers)),
        "safe_state_exit_eligible": eligible,
        "status": status,
        "authority_policy_id": RECOVERY_AUTHORITY_POLICY_ID,
        "fault_cleared_does_not_imply_full_recovery": True,
        "may_restore_resources": False,
        "may_restore_system_health": False,
        "may_remove_load_sheds": False,
        "may_clear_other_faults": False,
        "safe_state_exit_automatic": False,
    }
    packet["assessment_hash"] = _hash(packet, "AXM-POST-CLEARANCE-RECOVERY-ASSESSMENT-V1")
    return packet


def _validate_assessment_hash(assessment: dict[str, Any]) -> None:
    if assessment.get("schema") != "axm.post-clearance-recovery-assessment.v1":
        raise ValueError("unsupported post-clearance recovery assessment")
    raw = copy.deepcopy(assessment)
    claimed = raw.pop("assessment_hash", None)
    if claimed != _hash(raw, "AXM-POST-CLEARANCE-RECOVERY-ASSESSMENT-V1"):
        raise ValueError("post-clearance recovery assessment hash mismatch")


def build_safe_state_exit_authorization(
    assessment: dict[str, Any],
    *,
    source_ref: str,
    actor_role_ids: list[str],
    evidence_ids: list[str],
    decision: str = "authorize_safe_state_exit",
) -> dict[str, Any]:
    _validate_assessment_hash(assessment)
    if assessment.get("safe_state_exit_eligible") is not True:
        raise PermissionError("recovery assessment is not eligible for safe-state exit")
    if assessment.get("status") not in {
        "DEGRADED_SAFE_RECOVERY_RELEASE_ELIGIBLE",
        "NOMINAL_RECOVERY_RELEASE_ELIGIBLE",
    }:
        raise PermissionError("recovery assessment status does not permit safe-state exit")
    roles = sorted({str(v) for v in actor_role_ids if str(v).strip()})
    evidence = sorted({str(v) for v in evidence_ids if str(v).strip()})
    source = str(source_ref or "").strip()
    if "mission_commander" not in roles:
        raise PermissionError("safe-state exit requires mission commander authorization")
    if decision != "authorize_safe_state_exit":
        raise PermissionError("safe-state exit was not authorized")
    if not source:
        raise ValueError("safe-state exit authorization requires source_ref")
    if not evidence:
        raise ValueError("safe-state exit authorization requires evidence")

    packet = {
        "schema": "axm.safe-state-exit-authorization-receipt.v1",
        "version": RECOVERY_VERSION,
        "authorization_id": _hash({
            "assessment_hash": assessment.get("assessment_hash"),
            "state_hash_before": assessment.get("state_hash_assessed"),
            "source_ref": source,
            "actor_role_ids": roles,
            "evidence_ids": evidence,
            "decision": decision,
        }, "AXM-SAFE-STATE-EXIT-AUTHORIZATION-ID-V1"),
        "assessment_hash": assessment.get("assessment_hash"),
        "state_hash_before": assessment.get("state_hash_assessed"),
        "source_ref": source,
        "actor_role_ids": roles,
        "evidence_ids": evidence,
        "decision": decision,
        "authority_policy_id": RECOVERY_AUTHORITY_POLICY_ID,
        "truth_status": "simulation_policy_candidate_not_canon",
    }
    packet["authorization_hash"] = _hash(packet, "AXM-SAFE-STATE-EXIT-AUTHORIZATION-V1")
    return packet


def _validate_authorization(
    authorization: dict[str, Any],
    *,
    assessment: dict[str, Any],
) -> None:
    if authorization.get("schema") != "axm.safe-state-exit-authorization-receipt.v1":
        raise ValueError("unsupported safe-state exit authorization")
    raw = copy.deepcopy(authorization)
    claimed = raw.pop("authorization_hash", None)
    if claimed != _hash(raw, "AXM-SAFE-STATE-EXIT-AUTHORIZATION-V1"):
        raise ValueError("safe-state exit authorization hash mismatch")
    if authorization.get("assessment_hash") != assessment.get("assessment_hash"):
        raise ValueError("safe-state exit authorization assessment mismatch")
    if authorization.get("state_hash_before") != assessment.get("state_hash_assessed"):
        raise ValueError("safe-state exit authorization state hash mismatch")
    if authorization.get("authority_policy_id") != RECOVERY_AUTHORITY_POLICY_ID:
        raise PermissionError("unsupported post-clearance recovery authority policy")
    if authorization.get("decision") != "authorize_safe_state_exit":
        raise PermissionError("safe-state exit was not authorized")
    roles = {str(v) for v in authorization.get("actor_role_ids", []) if v}
    if "mission_commander" not in roles:
        raise PermissionError("safe-state exit requires mission commander authorization")
    if not authorization.get("evidence_ids"):
        raise ValueError("safe-state exit authorization evidence is missing")


def verify_recovery_chain(
    ship_state: dict[str, Any],
    clearance_apply_receipt: dict[str, Any],
    assessment: dict[str, Any],
    authorization: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        _validate_assessment_hash(assessment)
        replay = build_recovery_assessment(
            ship_state,
            clearance_apply_receipt,
            source_ref=str(assessment.get("source_ref") or ""),
            evidence_ids=list(assessment.get("evidence_ids") or []),
            independent_check_ids=list(assessment.get("independent_check_ids") or []),
        )
        if replay != assessment:
            raise ValueError("recovery assessment does not semantically replay from authoritative state")
        if authorization is not None:
            _validate_authorization(authorization, assessment=assessment)
        return {
            "schema": "axm.post-clearance-recovery-chain-verification.v1",
            "version": RECOVERY_VERSION,
            "status": "PASS",
            "assessment_hash": assessment.get("assessment_hash"),
            "authorization_hash": authorization.get("authorization_hash") if authorization else None,
            "state_hash_assessed": assessment.get("state_hash_assessed"),
        }
    except (ValueError, PermissionError, TypeError, KeyError) as exc:
        return {
            "schema": "axm.post-clearance-recovery-chain-verification.v1",
            "version": RECOVERY_VERSION,
            "status": "FAIL",
            "reason": str(exc),
            "assessment_hash": assessment.get("assessment_hash") if isinstance(assessment, dict) else None,
        }


def _state_payload_excluding_release_bookkeeping(state: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(state)
    payload.pop("mode", None)
    payload.pop("state_history", None)
    payload.pop("state_hash", None)
    return payload


def apply_safe_state_exit(
    ship_state: dict[str, Any],
    *,
    clearance_apply_receipt: dict[str, Any],
    assessment: dict[str, Any],
    authorization_receipt: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    chain = verify_recovery_chain(
        ship_state,
        clearance_apply_receipt,
        assessment,
        authorization_receipt,
    )
    if chain.get("status") != "PASS":
        raise ValueError("post-clearance recovery chain failed: " + str(chain.get("reason")))
    if assessment.get("safe_state_exit_eligible") is not True:
        raise PermissionError("recovery assessment does not authorize safe-state exit")
    if ship_state.get("state_hash") != assessment.get("state_hash_assessed"):
        raise ValueError("authoritative ship state changed after recovery assessment")
    if ship_state.get("mode") != "safe_state":
        raise ValueError("ship is not currently in safe state")

    before_payload = _state_payload_excluding_release_bookkeeping(ship_state)
    updated = copy.deepcopy(ship_state)
    updated["mode"] = "nominal"
    ship._set_safe_state_if_needed(updated)
    if updated.get("mode") == "safe_state":
        raise ValueError("safe-state exit rejected because live safety evaluation re-entered safe state")

    after_payload = _state_payload_excluding_release_bookkeeping(updated)
    if after_payload != before_payload:
        raise ValueError("safe-state exit attempted to modify residual ship state")

    ship._append_state_history(
        updated,
        f"apply_verified_safe_state_exit:{clearance_apply_receipt.get('failure_mode_id')}",
    )
    updated["state_hash"] = ship.state_hash(updated)
    if ship.verify_ship_state(updated).get("valid") is not True:
        raise ValueError("post-recovery ship state failed verification")

    receipt = {
        "schema": "axm.safe-state-exit-apply-receipt.v1",
        "version": RECOVERY_VERSION,
        "status": "APPLIED_VERIFIED_SAFE_STATE_EXIT",
        "source_failure_id": clearance_apply_receipt.get("failure_mode_id"),
        "source_system_id": clearance_apply_receipt.get("system_id"),
        "clearance_apply_receipt_hash": clearance_apply_receipt.get("apply_receipt_hash"),
        "assessment_hash": assessment.get("assessment_hash"),
        "authorization_hash": authorization_receipt.get("authorization_hash"),
        "previous_receipt_hash": authorization_receipt.get("authorization_hash"),
        "state_hash_before": ship_state.get("state_hash"),
        "state_hash_after": updated.get("state_hash"),
        "mode_before": "safe_state",
        "mode_after": updated.get("mode"),
        "recovery_status": assessment.get("status"),
        "residual_state_preserved": True,
        "resource_values_restored": False,
        "system_health_restored_by_exit": False,
        "load_sheds_removed_by_exit": False,
        "other_faults_cleared_by_exit": False,
        "authority_policy_id": RECOVERY_AUTHORITY_POLICY_ID,
    }
    receipt["apply_receipt_hash"] = _hash(receipt, "AXM-SAFE-STATE-EXIT-APPLY-RECEIPT-V1")
    return updated, receipt
