from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from . import ship_blueprint as ship
from .post_clearance_recovery import (
    _residual_state_snapshot,
    apply_safe_state_exit,
)


READINESS_VERSION = "0.11.0-candidate"
READINESS_AUTHORITY_POLICY_ID = "axm.operational-readiness-authority-policy.candidate.v1"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any, domain: str) -> str:
    return hashlib.sha256(f"{domain}|{_canonical(value)}".encode("utf-8")).hexdigest()


def _number(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number or abs(number) == float("inf"):
        return default
    return number


def _system(state: dict[str, Any], system_id: str) -> dict[str, Any]:
    row = state.get("system_health", {}).get(system_id, {})
    return row if isinstance(row, dict) else {}


def _system_faults(state: dict[str, Any], system_id: str) -> list[str]:
    return sorted({str(v) for v in _system(state, system_id).get("active_fault_ids", []) if v})


def _state_payload_excluding_release_bookkeeping(state: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(state)
    payload.pop("mode", None)
    payload.pop("state_history", None)
    payload.pop("state_hash", None)
    return payload


def build_operational_readiness_contract(
    recovery_contract: dict[str, Any],
) -> dict[str, Any]:
    if recovery_contract.get("schema") != "axm.post-clearance-recovery-contract.v1":
        raise ValueError("unsupported post-clearance recovery contract")
    upstream_ready = (
        recovery_contract.get("status")
        == "RECOVERY_ENGINE_AVAILABLE_AFTER_APPLIED_VERIFIED_CLEARANCE"
    )
    packet = {
        "schema": "axm.operational-readiness-contract.v1",
        "version": READINESS_VERSION,
        "contract_id": (
            f"operational-readiness:{recovery_contract.get('source_failure_id')}:v1"
        ),
        "source_failure_id": recovery_contract.get("source_failure_id"),
        "source_system_id": recovery_contract.get("source_system_id"),
        "recovery_contract_id": recovery_contract.get("contract_id"),
        "recovery_contract_hash": recovery_contract.get("contract_hash"),
        "authority_policy_id": READINESS_AUTHORITY_POLICY_ID,
        "status": (
            "OPERATIONAL_RELEASE_ENGINE_AVAILABLE_AFTER_VERIFIED_RECOVERY_CHAIN"
            if upstream_ready
            else "HOLD_UPSTREAM_RECOVERY_CONTRACT"
        ),
        "required_inputs": [
            "authoritative_safe_state_ship_state",
            "verified_clearance_apply_receipt",
            "verified_post_clearance_recovery_assessment",
            "mission_commander_safe_state_exit_authorization",
        ],
        "release_semantics": (
            "validate_safe_state_exit_then_classify_final_operating_mode_from_residual_truth"
        ),
        "mode_policy": {
            "residuals_present": "degraded_operations",
            "no_residuals_present": "nominal",
            "safe_state": "retained_when_live_safety_evaluation_fails",
            "truth_status": "simulation_policy_candidate_not_canon",
        },
        "capability_envelope_policy": (
            "read_only_operation_availability_and_hold_classification_not_execution"
        ),
        "may_claim_nominal_with_residuals": False,
        "may_restore_resources": False,
        "may_restore_system_health": False,
        "may_remove_load_sheds": False,
        "may_clear_other_faults": False,
        "may_execute_operation": False,
        "renderer_may_apply_operational_release": False,
    }
    packet["contract_hash"] = _hash(
        packet,
        "AXM-OPERATIONAL-READINESS-CONTRACT-V1",
    )
    return packet


def build_operational_readiness_contract_catalog(
    recovery_catalog: dict[str, Any],
) -> dict[str, Any]:
    if recovery_catalog.get("schema") != "axm.post-clearance-recovery-contract-catalog.v1":
        raise ValueError("unsupported post-clearance recovery contract catalog")
    rows = [
        build_operational_readiness_contract(row)
        for row in recovery_catalog.get("contracts", [])
        if isinstance(row, dict)
    ]
    packet = {
        "schema": "axm.operational-readiness-contract-catalog.v1",
        "version": READINESS_VERSION,
        "contract_count": len(rows),
        "contracts": rows,
        "authority": "contract_and_engine_availability_only",
        "operationally_released": False,
        "may_modify_presentation_runtime": False,
        "may_execute_operation": False,
        "may_claim_nominal_with_residuals": False,
    }
    packet["catalog_hash"] = _hash(
        packet,
        "AXM-OPERATIONAL-READINESS-CONTRACT-CATALOG-V1",
    )
    return packet


def derive_post_recovery_operating_mode(
    recovery_assessment: dict[str, Any],
) -> str:
    if recovery_assessment.get("schema") != "axm.post-clearance-recovery-assessment.v1":
        raise ValueError("unsupported post-clearance recovery assessment")
    if recovery_assessment.get("safe_state_exit_eligible") is not True:
        raise PermissionError("recovery assessment is not eligible for operational release")

    snapshot = recovery_assessment.get("residual_state_snapshot", {})
    residuals = sorted(
        {
            str(v)
            for v in snapshot.get("residual_indicators", [])
            if str(v).strip()
        }
    )
    status = recovery_assessment.get("status")
    if status == "DEGRADED_SAFE_RECOVERY_RELEASE_ELIGIBLE":
        if not residuals:
            raise ValueError(
                "degraded recovery status requires at least one residual indicator"
            )
        return "degraded_operations"
    if status == "NOMINAL_RECOVERY_RELEASE_ELIGIBLE":
        if residuals:
            raise ValueError("nominal recovery status cannot contain residual indicators")
        return "nominal"
    raise PermissionError("recovery assessment status does not permit operational release")


def _operation_row(
    operation_id: str,
    label: str,
    *,
    blockers: list[str],
    limits: list[str],
    evidence_basis: list[str],
) -> dict[str, Any]:
    normalized_blockers = sorted({str(v) for v in blockers if str(v).strip()})
    normalized_limits = sorted(
        {
            str(v)
            for v in limits
            if str(v).strip() and str(v) not in normalized_blockers
        }
    )
    status = (
        "HOLD"
        if normalized_blockers
        else "AVAILABLE_WITH_LIMITS"
        if normalized_limits
        else "AVAILABLE"
    )
    return {
        "operation_id": operation_id,
        "label": label,
        "status": status,
        "blockers": normalized_blockers,
        "limits": normalized_limits,
        "evidence_basis": sorted(
            {str(v) for v in evidence_basis if str(v).strip()}
        ),
        "may_execute": False,
        "may_override_hold": False,
    }


def _derive_operation_rows(
    state: dict[str, Any],
    residual_indicators: list[str],
) -> list[dict[str, Any]]:
    residuals = sorted({str(v) for v in residual_indicators if str(v).strip()})
    residual_set = set(residuals)
    evaluation = ship.evaluate_ship(state)
    survival_supported = (
        evaluation.get("crew_survival_state_currently_supported") is True
    )
    operating_mode = str(state.get("mode") or "unknown")
    shed_loads = set(state.get("power", {}).get("shed_loads", []))
    structure = state.get("structure", {})
    navigation = state.get("navigation", {})
    communications = state.get("communications", {})
    radiation = state.get("radiation", {})
    command = state.get("command", {})
    crew = state.get("crew", {})

    rows: list[dict[str, Any]] = []

    life_limits = sorted(
        residual_set
        & {
            "pressure_boundary_non_nominal",
            "pressure_leak_remains",
            "co2_removal_degraded",
            "oxygen_generation_degraded",
            "water_recovery_degraded",
            "water_quality_non_nominal",
            "radiation_shelter_active",
        }
    )
    if operating_mode == "degraded_operations":
        life_limits.append("degraded_operating_mode")
    rows.append(
        _operation_row(
            "life_support_monitoring",
            "Life-support monitoring and stabilization",
            blockers=[] if survival_supported else ["crew_survival_state_not_supported"],
            limits=life_limits,
            evidence_basis=[
                "axm.ship-evaluation.v1",
                "post_clearance_residual_state_snapshot",
            ],
        )
    )

    maintenance_limits = list(residuals) if operating_mode == "degraded_operations" else []
    rows.append(
        _operation_row(
            "routine_internal_maintenance",
            "Routine internal maintenance",
            blockers=[] if survival_supported else ["crew_survival_state_not_supported"],
            limits=maintenance_limits,
            evidence_basis=[
                "authoritative_system_health",
                "authoritative_maintenance_state",
                "post_clearance_residual_state_snapshot",
            ],
        )
    )

    science = _system(state, "science_payload_and_analysis")
    science_blockers: list[str] = []
    science_limits: list[str] = []
    if "science_payload_and_analysis" in shed_loads:
        science_blockers.append("science_payload_load_shed")
    if _system_faults(state, "science_payload_and_analysis"):
        science_blockers.append("science_payload_active_fault")
    if _number(science.get("availability"), 1.0) <= 0.0 or _number(
        science.get("health"), 1.0
    ) <= 0.2:
        science_blockers.append("science_payload_unavailable")
    if science.get("mode", "nominal") != "nominal":
        science_limits.append("science_payload_non_nominal")
    if _number(science.get("availability"), 1.0) < 1.0:
        science_limits.append("science_payload_availability_degraded")
    if operating_mode == "degraded_operations":
        science_limits.append("degraded_operating_mode")
    if "communications_degraded" in residual_set or "telemetry_visibility_degraded" in residual_set:
        science_limits.append("science_data_return_degraded")
    rows.append(
        _operation_row(
            "science_payload_operations",
            "Science payload operations",
            blockers=science_blockers,
            limits=science_limits,
            evidence_basis=[
                "system_health.science_payload_and_analysis",
                "power.shed_loads",
                "communications_state",
            ],
        )
    )

    robotics = _system(state, "robotics_and_probe_operations")
    robotics_blockers: list[str] = []
    robotics_limits: list[str] = []
    if "robotics_and_probe_operations" in shed_loads:
        robotics_blockers.append("robotics_load_shed")
    if _system_faults(state, "robotics_and_probe_operations"):
        robotics_blockers.append("robotics_active_fault")
    if _number(robotics.get("availability"), 1.0) <= 0.0 or _number(
        robotics.get("health"), 1.0
    ) <= 0.2:
        robotics_blockers.append("robotics_unavailable")
    if _number(communications.get("availability"), 1.0) <= 0.0:
        robotics_blockers.append("communications_unavailable_for_robotics")
    if robotics.get("mode", "nominal") != "nominal":
        robotics_limits.append("robotics_non_nominal")
    if _number(communications.get("availability"), 1.0) < 1.0:
        robotics_limits.append("robotics_link_degraded")
    if _number(communications.get("telemetry_visibility_fraction"), 1.0) < 1.0:
        robotics_limits.append("robotics_telemetry_visibility_degraded")
    if operating_mode == "degraded_operations":
        robotics_limits.append("degraded_operating_mode")
    rows.append(
        _operation_row(
            "robotics_probe_operations",
            "Robotics and probe operations",
            blockers=robotics_blockers,
            limits=robotics_limits,
            evidence_basis=[
                "system_health.robotics_and_probe_operations",
                "power.shed_loads",
                "communications_state",
            ],
        )
    )

    nav_blockers: list[str] = []
    nav_limits: list[str] = []
    nav_uncertainty = _number(navigation.get("navigation_uncertainty_km"), 999.0)
    pointing = _number(navigation.get("pointing_performance_multiplier"), 0.0)
    if navigation.get("propulsion_available") is False:
        nav_blockers.append("propulsion_unavailable")
    if _system_faults(state, "gnc"):
        nav_blockers.append("gnc_active_fault")
    if _system_faults(state, "reaction_control"):
        nav_blockers.append("reaction_control_active_fault")
    if nav_uncertainty >= 5.0:
        nav_blockers.append("navigation_uncertainty_above_candidate_hold_threshold")
    if pointing <= 0.5:
        nav_blockers.append("pointing_below_candidate_hold_threshold")
    if nav_uncertainty > 1.0:
        nav_limits.append("navigation_uncertainty_elevated")
    if pointing < 1.0:
        nav_limits.append("pointing_performance_degraded")
    if _system(state, "gnc").get("mode", "nominal") != "nominal":
        nav_limits.append("gnc_non_nominal")
    if _system(state, "reaction_control").get("mode", "nominal") != "nominal":
        nav_limits.append("reaction_control_non_nominal")
    if operating_mode == "degraded_operations":
        nav_limits.append("degraded_operating_mode")
    rows.append(
        _operation_row(
            "precision_navigation_maneuver",
            "Precision navigation maneuver",
            blockers=nav_blockers,
            limits=nav_limits,
            evidence_basis=[
                "navigation_state",
                "system_health.gnc",
                "system_health.reaction_control",
                "candidate_thresholds_not_real_vehicle_certification",
            ],
        )
    )

    docking = _system(state, "docking_airlock_eva")
    docking_blockers: list[str] = []
    docking_limits: list[str] = []
    if navigation.get("propulsion_available") is False:
        docking_blockers.append("propulsion_unavailable")
    if docking.get("mode", "nominal") != "nominal":
        docking_blockers.append("docking_transfer_system_non_nominal")
    if _system_faults(state, "docking_airlock_eva"):
        docking_blockers.append("docking_transfer_active_fault")
    if structure.get("pressure_boundary_state") != "nominal":
        docking_blockers.append("pressure_boundary_non_nominal")
    if _number(structure.get("health"), 1.0) < 0.8:
        docking_blockers.append("structure_below_candidate_docking_threshold")
    if nav_uncertainty > 1.0:
        docking_limits.append("navigation_uncertainty_elevated")
    if pointing < 1.0:
        docking_limits.append("pointing_performance_degraded")
    if _number(structure.get("health"), 1.0) < 1.0:
        docking_limits.append("structure_health_degraded")
    if operating_mode == "degraded_operations":
        docking_limits.append("degraded_operating_mode")
    rows.append(
        _operation_row(
            "docking_and_transfer",
            "Docking and transfer",
            blockers=docking_blockers,
            limits=docking_limits,
            evidence_basis=[
                "system_health.docking_airlock_eva",
                "structure_state",
                "navigation_state",
                "candidate_thresholds_not_real_vehicle_certification",
            ],
        )
    )

    eva_blockers: list[str] = []
    eva_limits: list[str] = []
    if radiation.get("shelter_active") is True:
        eva_blockers.append("radiation_shelter_active")
    if structure.get("pressure_boundary_state") != "nominal":
        eva_blockers.append("pressure_boundary_non_nominal")
    if _number(structure.get("health"), 1.0) < 0.8:
        eva_blockers.append("structure_below_candidate_eva_threshold")
    if int(_number(crew.get("available_human_crew"), 0.0)) <= 0:
        eva_blockers.append("no_available_human_crew")
    if structure.get("isolated_rooms"):
        eva_limits.append("isolated_rooms_remain")
    if _number(structure.get("health"), 1.0) < 1.0:
        eva_limits.append("structure_health_degraded")
    if _number(radiation.get("environment_index"), 1.0) > 1.0:
        eva_limits.append("radiation_environment_elevated")
    if operating_mode == "degraded_operations":
        eva_limits.append("degraded_operating_mode")
    rows.append(
        _operation_row(
            "eva_external_operations",
            "EVA and external operations",
            blockers=eva_blockers,
            limits=eva_limits,
            evidence_basis=[
                "structure_state",
                "radiation_state",
                "crew_availability",
                "candidate_thresholds_not_real_vehicle_certification",
            ],
        )
    )

    comm_blockers: list[str] = []
    comm_limits: list[str] = []
    comm_availability = _number(communications.get("availability"), 0.0)
    telemetry_visibility = _number(
        communications.get("telemetry_visibility_fraction"), 0.0
    )
    if comm_availability <= 0.0:
        comm_blockers.append("communications_unavailable")
    if _system_faults(state, "communications"):
        comm_blockers.append("communications_active_fault")
    if pointing <= 0.2:
        comm_blockers.append("communications_pointing_below_candidate_hold_threshold")
    if comm_availability < 1.0:
        comm_limits.append("communications_availability_degraded")
    if telemetry_visibility < 1.0:
        comm_limits.append("telemetry_visibility_degraded")
    if pointing < 1.0:
        comm_limits.append("pointing_performance_degraded")
    if operating_mode == "degraded_operations":
        comm_limits.append("degraded_operating_mode")
    rows.append(
        _operation_row(
            "high_bandwidth_communications",
            "High-bandwidth communications",
            blockers=comm_blockers,
            limits=comm_limits,
            evidence_basis=[
                "communications_state",
                "navigation_pointing_state",
                "candidate_thresholds_not_real_vehicle_certification",
            ],
        )
    )

    irreversible_blockers: list[str] = []
    if operating_mode != "nominal":
        irreversible_blockers.append("operating_mode_not_nominal")
    if residuals:
        irreversible_blockers.append("residual_state_remains")
    if command.get("pending_recall") is not None:
        irreversible_blockers.append("command_recall_remains")
    if command.get("held_irreversible_actions"):
        irreversible_blockers.append("irreversible_action_holds_remain")
    active_fault_count = sum(
        len(_system_faults(state, system_id))
        for system_id in state.get("system_health", {})
    )
    if active_fault_count:
        irreversible_blockers.append("active_faults_remain")
    rows.append(
        _operation_row(
            "irreversible_mission_commitment",
            "Irreversible mission commitment",
            blockers=irreversible_blockers,
            limits=[],
            evidence_basis=[
                "authoritative_operating_mode",
                "post_clearance_residual_state_snapshot",
                "command_state",
                "active_fault_state",
            ],
        )
    )

    return rows


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        status: sum(1 for row in rows if row.get("status") == status)
        for status in ("AVAILABLE", "AVAILABLE_WITH_LIMITS", "HOLD")
    }


def apply_operational_release(
    ship_state: dict[str, Any],
    *,
    clearance_apply_receipt: dict[str, Any],
    recovery_assessment: dict[str, Any],
    authorization_receipt: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    validated_state, safe_state_exit_receipt = apply_safe_state_exit(
        ship_state,
        clearance_apply_receipt=clearance_apply_receipt,
        assessment=recovery_assessment,
        authorization_receipt=authorization_receipt,
    )
    target_mode = derive_post_recovery_operating_mode(recovery_assessment)

    before_payload = _state_payload_excluding_release_bookkeeping(ship_state)
    validated_payload = _state_payload_excluding_release_bookkeeping(validated_state)
    if validated_payload != before_payload:
        raise ValueError(
            "safe-state exit validation attempted to modify residual ship state"
        )

    updated = copy.deepcopy(ship_state)
    updated["mode"] = target_mode
    ship._set_safe_state_if_needed(updated)
    if updated.get("mode") == "safe_state":
        raise ValueError(
            "operational release rejected because live safety evaluation requires safe state"
        )
    if updated.get("mode") != target_mode:
        raise ValueError("operational release mode classification was not preserved")

    if _state_payload_excluding_release_bookkeeping(updated) != before_payload:
        raise ValueError("operational release attempted to modify residual ship state")

    reason = (
        "apply_verified_operational_release:"
        f"{clearance_apply_receipt.get('failure_mode_id')}:{target_mode}"
    )
    ship._append_state_history(updated, reason)
    updated["state_hash"] = ship.state_hash(updated)
    if ship.verify_ship_state(updated).get("valid") is not True:
        raise ValueError("post-release operational ship state failed verification")

    residuals = sorted(
        {
            str(v)
            for v in recovery_assessment.get("residual_state_snapshot", {}).get(
                "residual_indicators", []
            )
            if str(v).strip()
        }
    )
    rows = _derive_operation_rows(updated, residuals)
    counts = _status_counts(rows)
    status = (
        "APPLIED_VERIFIED_DEGRADED_OPERATIONAL_RELEASE"
        if target_mode == "degraded_operations"
        else "APPLIED_VERIFIED_NOMINAL_OPERATIONAL_RELEASE"
    )
    receipt = {
        "schema": "axm.operational-release-apply-receipt.v1",
        "version": READINESS_VERSION,
        "status": status,
        "source_failure_id": clearance_apply_receipt.get("failure_mode_id"),
        "source_system_id": clearance_apply_receipt.get("system_id"),
        "clearance_apply_receipt_hash": clearance_apply_receipt.get(
            "apply_receipt_hash"
        ),
        "recovery_assessment_hash": recovery_assessment.get("assessment_hash"),
        "safe_state_exit_authorization_hash": authorization_receipt.get(
            "authorization_hash"
        ),
        "safe_state_exit_validation_receipt_hash": safe_state_exit_receipt.get(
            "apply_receipt_hash"
        ),
        "safe_state_exit_validation_state_hash": safe_state_exit_receipt.get(
            "state_hash_after"
        ),
        "previous_receipt_hash": safe_state_exit_receipt.get("apply_receipt_hash"),
        "state_hash_before": ship_state.get("state_hash"),
        "state_hash_after": updated.get("state_hash"),
        "mode_before": "safe_state",
        "mode_after": target_mode,
        "intermediate_nominal_state_persisted": False,
        "residual_indicators": residuals,
        "residuals_present": bool(residuals),
        "nominal_claim_allowed": target_mode == "nominal",
        "operation_status_counts": counts,
        "residual_state_preserved": True,
        "resource_values_restored": False,
        "system_health_restored_by_release": False,
        "load_sheds_removed_by_release": False,
        "other_faults_cleared_by_release": False,
        "may_execute_operation": False,
        "authority_policy_id": READINESS_AUTHORITY_POLICY_ID,
        "truth_status": "simulation_policy_candidate_not_canon",
    }
    receipt["apply_receipt_hash"] = _hash(
        receipt,
        "AXM-OPERATIONAL-RELEASE-APPLY-RECEIPT-V1",
    )
    return updated, receipt


def _validate_operational_release_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("schema") != "axm.operational-release-apply-receipt.v1":
        raise ValueError("unsupported operational release receipt")
    raw = copy.deepcopy(receipt)
    claimed = raw.pop("apply_receipt_hash", None)
    if claimed != _hash(raw, "AXM-OPERATIONAL-RELEASE-APPLY-RECEIPT-V1"):
        raise ValueError("operational release receipt hash mismatch")
    if receipt.get("authority_policy_id") != READINESS_AUTHORITY_POLICY_ID:
        raise PermissionError("unsupported operational readiness authority policy")
    if receipt.get("mode_before") != "safe_state":
        raise ValueError("operational release receipt has invalid starting mode")
    mode_after = receipt.get("mode_after")
    status = receipt.get("status")
    expected_status = {
        "degraded_operations": "APPLIED_VERIFIED_DEGRADED_OPERATIONAL_RELEASE",
        "nominal": "APPLIED_VERIFIED_NOMINAL_OPERATIONAL_RELEASE",
    }.get(mode_after)
    if expected_status is None or status != expected_status:
        raise ValueError("operational release status and mode do not match")
    residuals = receipt.get("residual_indicators")
    if not isinstance(residuals, list):
        raise ValueError("operational release residual indicators must be a list")
    if mode_after == "nominal" and residuals:
        raise ValueError("nominal operational release cannot retain residual indicators")
    if mode_after == "degraded_operations" and not residuals:
        raise ValueError("degraded operational release requires residual indicators")
    if receipt.get("intermediate_nominal_state_persisted") is not False:
        raise ValueError("operational release must not persist an intermediate nominal state")
    if receipt.get("residual_state_preserved") is not True:
        raise ValueError("operational release did not preserve residual state")
    if receipt.get("resource_values_restored") is not False:
        raise ValueError("operational release may not restore resources")
    if receipt.get("system_health_restored_by_release") is not False:
        raise ValueError("operational release may not restore system health")
    if receipt.get("load_sheds_removed_by_release") is not False:
        raise ValueError("operational release may not remove load sheds")
    if receipt.get("other_faults_cleared_by_release") is not False:
        raise ValueError("operational release may not clear other faults")
    if receipt.get("may_execute_operation") is not False:
        raise ValueError("operational release receipt cannot grant operation execution")


def build_operational_readiness_envelope(
    ship_state: dict[str, Any],
    operational_release_receipt: dict[str, Any],
) -> dict[str, Any]:
    if ship.verify_ship_state(ship_state).get("valid") is not True:
        raise ValueError("operational readiness requires a valid authoritative ship state")
    _validate_operational_release_receipt(operational_release_receipt)
    if ship_state.get("state_hash") != operational_release_receipt.get(
        "state_hash_after"
    ):
        raise ValueError("operational readiness state hash mismatch")
    if ship_state.get("mode") != operational_release_receipt.get("mode_after"):
        raise ValueError("operational readiness operating mode mismatch")

    snapshot = _residual_state_snapshot(ship_state)
    residuals = sorted(
        {
            str(v)
            for v in snapshot.get("residual_indicators", [])
            if str(v).strip()
        }
    )
    expected_residuals = sorted(
        {
            str(v)
            for v in operational_release_receipt.get("residual_indicators", [])
            if str(v).strip()
        }
    )
    if residuals != expected_residuals:
        raise ValueError("operational readiness residual-state replay mismatch")

    if ship_state.get("mode") == "nominal" and residuals:
        raise ValueError("authoritative ship state claims nominal while residuals remain")
    if ship_state.get("mode") == "degraded_operations" and not residuals:
        raise ValueError("degraded operating mode has no supporting residual state")

    rows = _derive_operation_rows(ship_state, residuals)
    counts = _status_counts(rows)
    if counts != operational_release_receipt.get("operation_status_counts"):
        raise ValueError("operational readiness counts do not replay from ship state")

    packet = {
        "schema": "axm.operational-readiness-envelope.v1",
        "version": READINESS_VERSION,
        "state_hash": ship_state.get("state_hash"),
        "operational_release_receipt_hash": operational_release_receipt.get(
            "apply_receipt_hash"
        ),
        "operating_mode": ship_state.get("mode"),
        "residual_indicators": residuals,
        "operation_count": len(rows),
        "operation_status_counts": counts,
        "operations": rows,
        "authority": "read_only_capability_envelope",
        "threshold_truth_status": (
            "simulation_policy_candidate_not_real_vehicle_certification"
        ),
        "may_execute_operation": False,
        "may_override_hold": False,
        "may_claim_nominal_with_residuals": False,
    }
    packet["envelope_hash"] = _hash(
        packet,
        "AXM-OPERATIONAL-READINESS-ENVELOPE-V1",
    )
    return packet


def inspect_operation_readiness(
    envelope: dict[str, Any],
    operation_id: str,
) -> dict[str, Any]:
    if envelope.get("schema") != "axm.operational-readiness-envelope.v1":
        raise ValueError("unsupported operational readiness envelope")
    raw = copy.deepcopy(envelope)
    claimed = raw.pop("envelope_hash", None)
    if claimed != _hash(raw, "AXM-OPERATIONAL-READINESS-ENVELOPE-V1"):
        raise ValueError("operational readiness envelope hash mismatch")
    target = str(operation_id or "").strip()
    for row in envelope.get("operations", []):
        if isinstance(row, dict) and row.get("operation_id") == target:
            packet = {
                "schema": "axm.operation-readiness-inspection.v1",
                "version": READINESS_VERSION,
                "envelope_hash": envelope.get("envelope_hash"),
                "operation": copy.deepcopy(row),
                "authority": "inspection_only",
                "may_execute": False,
            }
            packet["inspection_hash"] = _hash(
                packet,
                "AXM-OPERATION-READINESS-INSPECTION-V1",
            )
            return packet
    raise ValueError(f"unknown operational readiness operation: {target}")


def verify_operational_release_chain(
    original_safe_state: dict[str, Any],
    *,
    clearance_apply_receipt: dict[str, Any],
    recovery_assessment: dict[str, Any],
    authorization_receipt: dict[str, Any],
    released_state: dict[str, Any],
    operational_release_receipt: dict[str, Any],
) -> dict[str, Any]:
    try:
        replay_state, replay_receipt = apply_operational_release(
            original_safe_state,
            clearance_apply_receipt=clearance_apply_receipt,
            recovery_assessment=recovery_assessment,
            authorization_receipt=authorization_receipt,
        )
        if replay_state != released_state:
            raise ValueError(
                "operationally released state does not replay from the pinned chain"
            )
        if replay_receipt != operational_release_receipt:
            raise ValueError(
                "operational release receipt does not replay from the pinned chain"
            )
        envelope = build_operational_readiness_envelope(
            released_state,
            operational_release_receipt,
        )
        return {
            "schema": "axm.operational-release-chain-verification.v1",
            "version": READINESS_VERSION,
            "status": "PASS",
            "state_hash_after": released_state.get("state_hash"),
            "operational_release_receipt_hash": operational_release_receipt.get(
                "apply_receipt_hash"
            ),
            "operational_readiness_envelope_hash": envelope.get("envelope_hash"),
        }
    except (ValueError, PermissionError, TypeError, KeyError) as exc:
        return {
            "schema": "axm.operational-release-chain-verification.v1",
            "version": READINESS_VERSION,
            "status": "FAIL",
            "reason": str(exc),
            "state_hash_after": (
                released_state.get("state_hash")
                if isinstance(released_state, dict)
                else None
            ),
        }
