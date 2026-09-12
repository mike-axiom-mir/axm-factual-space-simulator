from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .repair_verification import verify_repair_attempt_receipts
from . import ship_blueprint as ship

CLEARANCE_VERSION = "0.8.0-candidate"
AUTHORITY_POLICY_ID = "axm.fault-clearance-authority-policy.candidate.v1"

EFFECT_RECONCILIATION_PATHS: dict[str, tuple[str, ...]] = {
    "generation_multiplier": ("system_health.electrical_power_generation.availability",),
    "battery_soc_delta": ("power.battery_energy_kwh",),
    "load_service_fraction": ("system_health.power_distribution.availability",),
    "thermal_capacity_multiplier": ("system_health.thermal_control.availability",),
    "pressure_leak_kpa_per_hour": ("atmosphere.pressure_leak_kpa_per_hour", "structure.pressure_boundary_state"),
    "structure_health_delta": ("structure.health", "system_health.primary_structure.health"),
    "sensor_health_delta": ("system_health.external_sensors.health",),
    "co2_removal_multiplier": ("atmosphere.co2_removal_multiplier",),
    "oxygen_generation_multiplier": ("atmosphere.oxygen_generation_multiplier",),
    "water_recovery_multiplier": ("water.recovery_multiplier",),
    "power_load_kw_delta": ("power.loads_kw.habitability_and_lighting",),
    "affected_zone_available": ("structure.isolated_rooms",),
    "cdh_capacity_multiplier": ("system_health.avionics_cdh.availability",),
    "telemetry_visibility_fraction": ("communications.telemetry_visibility_fraction",),
    "navigation_uncertainty_km_delta": ("navigation.navigation_uncertainty_km",),
    "pointing_performance_multiplier": ("navigation.pointing_performance_multiplier",),
    "communications_availability": ("communications.availability",),
    "propulsion_available": ("navigation.propulsion_available",),
    "docking_transfer_allowed": ("system_health.docking_airlock_eva.mode",),
    "radiation_index_delta": ("radiation.environment_index", "radiation.shelter_active"),
    "robotics_health_delta": ("system_health.robotics_and_probe_operations.health",),
    "available_human_crew_delta": ("crew.available_human_crew",),
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any, domain: str) -> str:
    return hashlib.sha256(f"{domain}|{_canonical(value)}".encode("utf-8")).hexdigest()


def required_reconciliation_paths(
    failure_mode: dict[str, Any],
    *,
    source_system_id: str | None = None,
) -> list[str]:
    effects = failure_mode.get("effects", {}) if isinstance(failure_mode, dict) else {}
    if not isinstance(effects, dict):
        raise ValueError("failure effects must be an object")
    paths: set[str] = set()
    unknown_effect_keys: list[str] = []
    for key in effects:
        mapped = EFFECT_RECONCILIATION_PATHS.get(str(key))
        if mapped is None:
            unknown_effect_keys.append(str(key))
        else:
            paths.update(mapped)
    if unknown_effect_keys:
        raise ValueError("no authoritative reconciliation mapping for effect keys: " + ", ".join(sorted(unknown_effect_keys)))
    system_id = str(source_system_id or failure_mode.get("system_id") or "")
    if not system_id:
        raise ValueError("source system id is required")
    paths.add(f"system_health.{system_id}.mode")
    return sorted(paths)


def build_clearance_apply_contract(
    repair_gate: dict[str, Any],
    *,
    command_level: str | None = None,
    primary_role_id: str | None = None,
) -> dict[str, Any]:
    if repair_gate.get("schema") != "axm.repair-verification-gate.v1":
        raise ValueError("unsupported repair gate")
    packet = {
        "schema": "axm.fault-clearance-apply-contract.v1",
        "version": CLEARANCE_VERSION,
        "contract_id": f"clearance-apply:{repair_gate.get('source_failure_id')}:v1",
        "source_failure_id": repair_gate.get("source_failure_id"),
        "source_system_id": repair_gate.get("source_system_id"),
        "repair_gate_id": repair_gate.get("gate_id"),
        "repair_gate_hash": repair_gate.get("gate_hash"),
        "command_level": command_level or "unknown",
        "primary_role_id": primary_role_id,
        "authority_policy_id": AUTHORITY_POLICY_ID,
        "required_inputs": [
            "verified_effective_repair_attempt",
            "fault_clearance_candidate",
            "authoritative_ship_state",
            "state_reconciliation_receipt",
            "fault_clearance_authorization_receipt",
        ],
        "apply_semantics": "atomic_verified_state_reconciliation_plus_fault_status_clearance",
        "status": (
            "ENGINE_AVAILABLE_REQUIRES_VERIFIED_CANDIDATE_AND_LIVE_SHIP_STATE"
            if repair_gate.get("status") == "READY_FOR_EXTERNAL_REPAIR_PLAN"
            else "HOLD_UPSTREAM_REPAIR_GATE"
        ),
        "candidate_authority_policy": {
            "advisory": "primary procedure role authorization required",
            "command_required": "mission commander plus primary procedure role authorization required",
            "if_primary_role_is_mission_commander": "single mission commander authorization satisfies both role groups",
            "truth_status": "simulation_policy_candidate_not_canon",
        },
        "fault_cleared": False,
        "may_apply_without_verified_candidate": False,
        "may_apply_without_state_hash_match": False,
        "may_infer_restored_values": False,
        "may_clear_unrelated_faults": False,
    }
    packet["contract_hash"] = _hash(packet, "AXM-FAULT-CLEARANCE-APPLY-CONTRACT-V1")
    return packet


def build_clearance_apply_contract_catalog(
    repair_gate_catalog: dict[str, Any],
    procedure_catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if repair_gate_catalog.get("schema") != "axm.repair-verification-gate-catalog.v1":
        raise ValueError("unsupported repair gate catalog")
    procedures: dict[str, dict[str, Any]] = {}
    if isinstance(procedure_catalog, dict):
        for row in procedure_catalog.get("procedures", []):
            if isinstance(row, dict) and row.get("source_failure_id"):
                procedures[str(row["source_failure_id"])] = row
    rows = []
    for gate in repair_gate_catalog.get("gates", []):
        if not isinstance(gate, dict):
            continue
        proc = procedures.get(str(gate.get("source_failure_id")), {})
        rows.append(build_clearance_apply_contract(
            gate,
            command_level=proc.get("source_command_level"),
            primary_role_id=proc.get("primary_role_id"),
        ))
    packet = {
        "schema": "axm.fault-clearance-apply-contract-catalog.v1",
        "version": CLEARANCE_VERSION,
        "contract_count": len(rows),
        "contracts": rows,
        "authority": "contract_and_engine_availability_only",
        "fault_cleared": False,
        "may_modify_presentation_runtime": False,
    }
    packet["catalog_hash"] = _hash(packet, "AXM-FAULT-CLEARANCE-APPLY-CONTRACT-CATALOG-V1")
    return packet


def _validate_candidate(candidate: dict[str, Any], attempt: dict[str, Any]) -> None:
    if candidate.get("schema") != "axm.fault-clearance-candidate.v1":
        raise ValueError("unsupported fault clearance candidate")
    raw = copy.deepcopy(candidate)
    claimed = raw.pop("candidate_hash", None)
    if claimed != _hash(raw, "AXM-FAULT-CLEARANCE-CANDIDATE-V1"):
        raise ValueError("fault clearance candidate hash mismatch")
    if candidate.get("status") != "CLEARANCE_CANDIDATE_REQUIRES_AUTHORITATIVE_APPLY":
        raise ValueError("candidate is not awaiting authoritative apply")
    if candidate.get("fault_clearance_eligible") is not True or candidate.get("fault_cleared") is not False:
        raise ValueError("candidate does not preserve clearance eligibility boundary")
    if attempt.get("status") != "VERIFIED_EFFECTIVE_CLEARANCE_ELIGIBLE":
        raise ValueError("repair attempt is not verified effective")
    if verify_repair_attempt_receipts(attempt).get("status") != "PASS":
        raise ValueError("repair attempt receipt chain failed")
    if candidate.get("attempt_id") != attempt.get("attempt_id"):
        raise ValueError("candidate/attempt id mismatch")
    if candidate.get("verification_receipt_hash") != attempt.get("previous_receipt_hash"):
        raise ValueError("candidate does not pin the repair verification receipt")
    if candidate.get("source_failure_id") != attempt.get("source_failure_id"):
        raise ValueError("candidate/attempt failure mismatch")
    if candidate.get("source_system_id") != attempt.get("source_system_id"):
        raise ValueError("candidate/attempt system mismatch")


def _validate_procedure_definition(procedure: dict[str, Any]) -> None:
    if procedure.get("schema") != "axm.failure-procedure-definition.v1":
        raise ValueError("unsupported failure procedure definition")
    raw = copy.deepcopy(procedure)
    claimed = raw.pop("procedure_hash", None)
    if claimed != _hash(raw, "AXM-FAILURE-PROCEDURE-DEFINITION-V1"):
        raise ValueError("failure procedure definition hash mismatch")


def _validate_attempt_identity(attempt: dict[str, Any]) -> None:
    required = {
        "attempt_id", "gate_hash", "procedure_session_id", "repair_plan_receipt",
        "actor_role_ids", "source_failure_id", "source_system_id",
    }
    missing = sorted(required - set(attempt))
    if missing:
        raise ValueError("repair attempt identity missing: " + ", ".join(missing))
    expected = _hash({
        "gate_hash": attempt.get("gate_hash"),
        "procedure_session_id": attempt.get("procedure_session_id"),
        "repair_plan_receipt": attempt.get("repair_plan_receipt"),
        "actor_role_ids": sorted({str(v) for v in attempt.get("actor_role_ids", []) if v}),
    }, "AXM-REPAIR-ATTEMPT-ID-V1")
    if attempt.get("attempt_id") != expected:
        raise ValueError("repair attempt id mismatch")
    plan = attempt.get("repair_plan_receipt")
    if not isinstance(plan, dict) or str(plan.get("target_system_id")) != str(attempt.get("source_system_id")):
        raise ValueError("repair attempt plan target no longer matches source system")
    if attempt.get("fault_cleared") is not False:
        raise ValueError("repair attempt must remain uncleared before authoritative apply")
    if attempt.get("repair_verified") is not True or attempt.get("verification_complete") is not True:
        raise ValueError("repair attempt lacks completed effective verification")
    if attempt.get("fault_clearance_eligible") is not True:
        raise ValueError("repair attempt is not clearance eligible")


def _validate_authorization(
    authorization: dict[str, Any],
    *,
    candidate: dict[str, Any],
    state_hash_before: str,
    command_level: str,
    primary_role_id: str,
) -> str:
    required = {"authorization_id", "source_ref", "candidate_hash", "state_hash_before", "decision", "actor_role_ids", "authority_policy_id"}
    missing = sorted(required - set(authorization))
    if missing:
        raise ValueError("clearance authorization receipt missing: " + ", ".join(missing))
    if authorization.get("candidate_hash") != candidate.get("candidate_hash"):
        raise ValueError("authorization candidate hash mismatch")
    if authorization.get("state_hash_before") != state_hash_before:
        raise ValueError("authorization state hash mismatch")
    if authorization.get("decision") != "authorize_fault_clearance_apply":
        raise PermissionError("fault clearance was not authorized")
    if authorization.get("authority_policy_id") != AUTHORITY_POLICY_ID:
        raise PermissionError("unsupported fault clearance authority policy")
    roles = {str(v) for v in authorization.get("actor_role_ids", []) if v}
    if not roles:
        raise PermissionError("authorization requires actor roles")
    if primary_role_id not in roles:
        raise PermissionError("primary procedure role must authorize fault clearance")
    if command_level == "command_required" and "mission_commander" not in roles:
        raise PermissionError("command-required fault clearance also needs mission commander authorization")
    receipt = copy.deepcopy(authorization)
    receipt["actor_role_ids"] = sorted(roles)
    return _hash(receipt, "AXM-FAULT-CLEARANCE-AUTHORIZATION-V1")
    if command_level == "command_required" and "mission_commander" not in roles:
        raise PermissionError("command-required fault clearance also needs mission commander authorization")
    receipt = copy.deepcopy(authorization)
    receipt["actor_role_ids"] = sorted(roles)
    return _hash(receipt, "AXM-FAULT-CLEARANCE-AUTHORIZATION-V1")


def _get_path(root: dict[str, Any], path: str) -> Any:
    cur: Any = root
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise ValueError(f"state reconciliation path does not exist: {path}")
        cur = cur[part]
    return cur


def _set_path(root: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur: Any = root
    for part in parts[:-1]:
        if not isinstance(cur, dict) or part not in cur:
            raise ValueError(f"state reconciliation path does not exist: {path}")
        cur = cur[part]
    if not isinstance(cur, dict) or parts[-1] not in cur:
        raise ValueError(f"state reconciliation path does not exist: {path}")
    cur[parts[-1]] = copy.deepcopy(value)


def _validate_verified_value(path: str, value: Any, state: dict[str, Any]) -> None:
    current = _get_path(state, path)
    if isinstance(current, bool):
        if not isinstance(value, bool):
            raise ValueError(f"verified value type mismatch at {path}")
        return
    if isinstance(current, (int, float)) and not isinstance(current, bool):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"verified value type mismatch at {path}")
        number = float(value)
        if not (number == number and abs(number) != float("inf")):
            raise ValueError(f"verified numeric value must be finite at {path}")
        if path.endswith((".availability", ".health", "_multiplier", "_fraction")) or path.endswith("pointing_performance_multiplier"):
            if not 0.0 <= number <= 1.0:
                raise ValueError(f"verified fractional state out of range at {path}")
        if path == "power.battery_energy_kwh":
            capacity = float(state.get("power", {}).get("battery_capacity_kwh", 0.0))
            if number < 0.0 or (capacity > 0.0 and number > capacity):
                raise ValueError("verified battery energy is outside pinned capacity")
        if path in {"atmosphere.pressure_leak_kpa_per_hour", "navigation.navigation_uncertainty_km", "radiation.environment_index"} and number < 0.0:
            raise ValueError(f"verified state cannot be negative at {path}")
        if path == "power.loads_kw.habitability_and_lighting" and number < 0.0:
            raise ValueError("verified load cannot be negative")
        if path == "crew.available_human_crew" and (number < 0.0 or int(number) != number):
            raise ValueError("verified available crew must be a non-negative integer")
        return
    if isinstance(current, str):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"verified string state is invalid at {path}")
        return
    if isinstance(current, list):
        if not isinstance(value, list):
            raise ValueError(f"verified list state is invalid at {path}")
        return
    if type(value) is not type(current):
        raise ValueError(f"verified value type mismatch at {path}")


def _validate_reconciliation(
    reconciliation: dict[str, Any],
    *,
    state: dict[str, Any],
    failure_mode: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    required = {"reconciliation_id", "source_ref", "candidate_hash", "state_hash_before", "source_failure_id", "source_system_id", "updates"}
    missing = sorted(required - set(reconciliation))
    if missing:
        raise ValueError("state reconciliation receipt missing: " + ", ".join(missing))
    if reconciliation.get("candidate_hash") != candidate.get("candidate_hash"):
        raise ValueError("reconciliation candidate hash mismatch")
    if reconciliation.get("state_hash_before") != state.get("state_hash"):
        raise ValueError("reconciliation state hash mismatch")
    if reconciliation.get("source_failure_id") != candidate.get("source_failure_id"):
        raise ValueError("reconciliation failure mismatch")
    if reconciliation.get("source_system_id") != candidate.get("source_system_id"):
        raise ValueError("reconciliation system mismatch")
    updates = reconciliation.get("updates")
    if not isinstance(updates, list):
        raise ValueError("reconciliation updates must be a list")
    required_paths = set(required_reconciliation_paths(failure_mode, source_system_id=str(candidate.get("source_system_id"))))
    supplied_paths = {str(row.get("path")) for row in updates if isinstance(row, dict) and row.get("path")}
    if supplied_paths != required_paths:
        missing_paths = sorted(required_paths - supplied_paths)
        extra_paths = sorted(supplied_paths - required_paths)
        parts = []
        if missing_paths:
            parts.append("missing paths: " + ", ".join(missing_paths))
        if extra_paths:
            parts.append("unapproved paths: " + ", ".join(extra_paths))
        raise ValueError("state reconciliation path set mismatch; " + "; ".join(parts))
    normalized = []
    for row in updates:
        if not isinstance(row, dict):
            raise ValueError("reconciliation update must be an object")
        path = str(row.get("path") or "")
        evidence_ids = row.get("evidence_ids")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            raise ValueError(f"reconciliation update requires evidence: {path}")
        if "expected_current_value" not in row or "verified_value" not in row:
            raise ValueError(f"reconciliation update missing values: {path}")
        actual = _get_path(state, path)
        if actual != row["expected_current_value"]:
            raise ValueError(f"stale reconciliation precondition at {path}")
        normalized_evidence = sorted({str(v) for v in evidence_ids if str(v).strip()})
        if not normalized_evidence:
            raise ValueError(f"reconciliation update requires non-empty evidence: {path}")
        _validate_verified_value(path, row["verified_value"], state)
        normalized.append({
            "path": path,
            "expected_current_value": copy.deepcopy(row["expected_current_value"]),
            "verified_value": copy.deepcopy(row["verified_value"]),
            "evidence_ids": normalized_evidence,
        })
    normalized.sort(key=lambda row: row["path"])
    receipt = copy.deepcopy(reconciliation)
    receipt["updates"] = normalized
    return normalized, _hash(receipt, "AXM-SHIP-STATE-RECONCILIATION-V1")


def _active_command_required_faults(state: dict[str, Any], registry: dict[str, Any]) -> list[tuple[str, str]]:
    modes = {
        str(row.get("id")): row
        for row in registry.get("failure_modes", [])
        if isinstance(row, dict) and row.get("id")
    }
    active: list[tuple[str, str]] = []
    for system_id, health in state.get("system_health", {}).items():
        if not isinstance(health, dict):
            continue
        for fault_id in health.get("active_fault_ids", []):
            mode = modes.get(str(fault_id))
            if isinstance(mode, dict) and mode.get("command_level") == "command_required":
                active.append((str(fault_id), str(system_id)))
    return sorted(active)


def apply_verified_fault_clearance(
    state: dict[str, Any],
    *,
    candidate: dict[str, Any],
    repair_attempt: dict[str, Any],
    procedure: dict[str, Any],
    reconciliation_receipt: dict[str, Any],
    authorization_receipt: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    state_check = ship.verify_ship_state(state)
    if state_check.get("valid") is not True:
        raise ValueError("authoritative ship state failed verification")
    _validate_candidate(candidate, repair_attempt)
    _validate_attempt_identity(repair_attempt)
    _validate_procedure_definition(procedure)

    failure_id = str(candidate.get("source_failure_id") or "")
    system_id = str(candidate.get("source_system_id") or "")
    if procedure.get("source_failure_id") != failure_id or procedure.get("source_system_id") != system_id:
        raise ValueError("procedure does not match clearance candidate")
    if procedure.get("procedure_id") != repair_attempt.get("procedure_id"):
        raise ValueError("repair attempt/procedure mismatch")
    command_level = str(procedure.get("source_command_level") or "unknown")
    primary_role_id = str(procedure.get("primary_role_id") or "")
    if command_level not in {"advisory", "command_required"}:
        raise ValueError("procedure command level is not eligible for authoritative clearance")
    if not primary_role_id:
        raise ValueError("procedure primary role is required for clearance authority")

    failure_registry = ship.load_failure_registry()
    modes = {row["id"]: row for row in failure_registry.get("failure_modes", []) if isinstance(row, dict) and row.get("id")}
    if failure_id not in modes:
        raise ValueError("fault clearance refers to an unknown failure mode")
    failure_mode = modes[failure_id]
    if str(failure_mode.get("system_id")) != system_id:
        raise ValueError("failure registry system does not match candidate")
    health = state.get("system_health", {}).get(system_id)
    if not isinstance(health, dict) or failure_id not in health.get("active_fault_ids", []):
        raise ValueError("fault is not active in authoritative ship state")

    for record in state.get("fault_ledger", []):
        if isinstance(record, dict) and record.get("record_type") == "verified_clearance" and record.get("candidate_hash") == candidate.get("candidate_hash"):
            raise ValueError("fault clearance candidate was already applied")

    auth_hash = _validate_authorization(
        authorization_receipt,
        candidate=candidate,
        state_hash_before=str(state.get("state_hash")),
        command_level=command_level,
        primary_role_id=primary_role_id,
    )
    updates, reconciliation_hash = _validate_reconciliation(
        reconciliation_receipt,
        state=state,
        failure_mode=failure_mode,
        candidate=candidate,
    )

    updated = copy.deepcopy(state)
    for row in updates:
        _set_path(updated, row["path"], row["verified_value"])

    active = updated["system_health"][system_id].get("active_fault_ids", [])
    updated["system_health"][system_id]["active_fault_ids"] = [v for v in active if v != failure_id]
    remaining_same_system = updated["system_health"][system_id].get("active_fault_ids", [])
    if remaining_same_system and updated["system_health"][system_id].get("mode") == "nominal":
        raise ValueError("reconciliation cannot mark a system nominal while other active faults remain")

    recall_cleared = False
    recall_retargeted_to = None
    pending = updated.get("command", {}).get("pending_recall")
    if isinstance(pending, dict) and pending.get("reason") == failure_id:
        other_command_faults = [row for row in _active_command_required_faults(updated, failure_registry) if row[0] != failure_id]
        if other_command_faults:
            next_fault_id, next_system_id = other_command_faults[0]
            updated["command"]["pending_recall"] = {
                "reason": next_fault_id,
                "summary": f"{next_system_id} fault still requires command review.",
                "held_irreversible_action": True,
                "reasserted_after_clearance_of": failure_id,
            }
            recall_retargeted_to = next_fault_id
        else:
            updated["command"]["pending_recall"] = None
            recall_cleared = True

    ship._append_fault(updated, {
        "record_type": "verified_clearance",
        "failure_mode_id": failure_id,
        "system_id": system_id,
        "candidate_hash": candidate.get("candidate_hash"),
        "repair_attempt_id": repair_attempt.get("attempt_id"),
        "repair_verification_receipt_hash": repair_attempt.get("previous_receipt_hash"),
        "authorization_receipt_hash": auth_hash,
        "reconciliation_receipt_hash": reconciliation_hash,
        "reconciled_paths": [row["path"] for row in updates],
        "pending_recall_cleared": recall_cleared,
        "pending_recall_retargeted_to": recall_retargeted_to,
        "fault_cleared": True,
        "repair_verified": True,
        "clearance_semantics": "verified_effective_repair_plus_exact_observed_state_reconciliation",
    })
    ship._set_safe_state_if_needed(updated)
    ship._append_state_history(updated, f"apply_verified_fault_clearance:{failure_id}")
    updated["state_hash"] = ship.state_hash(updated)

    post_check = ship.verify_ship_state(updated)
    if post_check.get("valid") is not True:
        raise ValueError("post-clearance ship state failed verification")

    receipt = {
        "schema": "axm.fault-clearance-apply-receipt.v1",
        "version": CLEARANCE_VERSION,
        "status": "APPLIED_VERIFIED_FAULT_CLEARANCE",
        "failure_mode_id": failure_id,
        "system_id": system_id,
        "candidate_hash": candidate.get("candidate_hash"),
        "repair_attempt_id": repair_attempt.get("attempt_id"),
        "state_hash_before": state.get("state_hash"),
        "state_hash_after": updated.get("state_hash"),
        "authorization_receipt_hash": auth_hash,
        "reconciliation_receipt_hash": reconciliation_hash,
        "reconciled_paths": [row["path"] for row in updates],
        "pending_recall_cleared": recall_cleared,
        "pending_recall_retargeted_to": recall_retargeted_to,
        "fault_cleared": True,
        "repair_verified": True,
        "may_clear_unrelated_faults": False,
        "safe_state_exit_automatic": False,
        "authority_policy_id": AUTHORITY_POLICY_ID,
    }
    receipt["apply_receipt_hash"] = _hash(receipt, "AXM-FAULT-CLEARANCE-APPLY-RECEIPT-V1")
    return updated, receipt
