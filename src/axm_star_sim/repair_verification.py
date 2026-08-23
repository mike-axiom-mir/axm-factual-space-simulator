from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .failure_procedures import verify_procedure_receipts

REPAIR_VERIFICATION_VERSION = "0.7.0-candidate"

def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def _hash(value: Any, domain: str) -> str:
    return hashlib.sha256(f"{domain}|{_canonical(value)}".encode("utf-8")).hexdigest()

def _by_failure(catalog: dict[str, Any] | None, key: str) -> dict[str, dict[str, Any]]:
    if not isinstance(catalog, dict):
        return {}
    rows = catalog.get(key, [])
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("source_failure_id")): row
        for row in rows
        if isinstance(row, dict) and row.get("source_failure_id")
    }

def build_repair_gate(
    procedure: dict[str, Any],
    topology: dict[str, Any] | None,
    *,
    index: int = 0,
) -> dict[str, Any]:
    if not isinstance(procedure, dict) or not procedure.get("source_failure_id"):
        raise ValueError("procedure with source_failure_id is required")
    failure_id = str(procedure["source_failure_id"])
    base = {
        "schema": "axm.repair-verification-gate.v1",
        "version": REPAIR_VERIFICATION_VERSION,
        "gate_id": f"repair-gate:{failure_id}:v1",
        "source_failure_index": index,
        "source_failure_id": failure_id,
        "source_system_id": procedure.get("source_system_id"),
        "procedure_id": procedure.get("procedure_id"),
        "procedure_hash": procedure.get("procedure_hash"),
        "topology_id": topology.get("topology_id") if isinstance(topology, dict) else None,
        "topology_hash": topology.get("topology_hash") if isinstance(topology, dict) else None,
        "required_receipt_sequence": [
            "completed_procedure_session",
            "repair_plan_receipt",
            "external_execution_receipt",
            "post_repair_verification_receipt",
            "authoritative_fault_clearance_apply",
        ],
        "component_specificity": (
            topology.get("component_specificity", {}).get("status")
            if isinstance(topology, dict)
            else None
        ),
        "authority": "repair_staging_and_verification_gate_only",
        "may_execute_repair": False,
        "may_modify_runtime": False,
        "may_consume_spares": False,
        "may_fabricate_repair_part": False,
        "may_clear_fault": False,
        "fault_cleared": False,
        "repair_verified": False,
        "verification_complete": False,
        "fault_clearance_eligible": False,
    }

    if procedure.get("status") != "PROCEDURE_AVAILABLE_FOR_REVIEW":
        base.update({
            "status": "HOLD_PROCEDURE_NOT_AVAILABLE",
            "hold_reason": procedure.get("status"),
        })
    elif not isinstance(topology, dict) or topology.get("status") != "TOPOLOGY_VIEW_AVAILABLE":
        base.update({
            "status": "HOLD_TOPOLOGY_NOT_AVAILABLE",
            "hold_reason": topology.get("status") if isinstance(topology, dict) else "missing_topology",
        })
    elif not str(topology.get("access", {}).get("status", "")).startswith("ACCESS_PATH_AVAILABLE"):
        base.update({
            "status": "HOLD_NO_PINNED_REPAIR_ACCESS",
            "hold_reason": topology.get("access", {}).get("status"),
        })
    else:
        base.update({
            "status": "READY_FOR_EXTERNAL_REPAIR_PLAN",
            "access_status": topology.get("access", {}).get("status"),
            "preferred_room_path": copy.deepcopy(topology.get("access", {}).get("preferred_room_path")),
            "truth_boundary": (
                "The simulator may stage a sourced repair plan and record external execution evidence. "
                "It does not invent a component repair method, execute the repair, or clear the fault."
            ),
        })
    base["gate_hash"] = _hash(base, "AXM-REPAIR-VERIFICATION-GATE-V1")
    return base

def build_repair_gate_catalog(
    procedure_catalog: dict[str, Any],
    topology_catalog: dict[str, Any],
) -> dict[str, Any]:
    if procedure_catalog.get("schema") != "axm.failure-procedure-catalog.v1":
        raise ValueError("unsupported procedure catalog")
    if topology_catalog.get("schema") != "axm.damage-topology-catalog.v1":
        raise ValueError("unsupported topology catalog")
    topology_by_failure = _by_failure(topology_catalog, "topologies")
    gates = [
        build_repair_gate(row, topology_by_failure.get(str(row.get("source_failure_id"))), index=index)
        for index, row in enumerate(procedure_catalog.get("procedures", []))
        if isinstance(row, dict) and row.get("source_failure_id")
    ]
    packet = {
        "schema": "axm.repair-verification-gate-catalog.v1",
        "version": REPAIR_VERIFICATION_VERSION,
        "gate_count": len(gates),
        "gates": gates,
        "authority": "repair_staging_and_verification_gate_only",
        "may_execute_repair": False,
        "may_modify_runtime": False,
        "may_consume_spares": False,
        "may_fabricate_repair_part": False,
        "may_clear_fault": False,
        "fault_cleared": False,
        "repair_verified": False,
    }
    packet["catalog_hash"] = _hash(packet, "AXM-REPAIR-VERIFICATION-GATE-CATALOG-V1")
    return packet

def stage_repair_attempt(
    gate: dict[str, Any],
    procedure_session: dict[str, Any],
    *,
    actor_role_ids: list[str],
    repair_plan_receipt: dict[str, Any],
) -> dict[str, Any]:
    if gate.get("status") != "READY_FOR_EXTERNAL_REPAIR_PLAN":
        raise ValueError("repair gate is not ready for plan intake")
    if procedure_session.get("status") != "PROCEDURE_COMPLETE_AWAIT_EXTERNAL_OUTCOME_VERIFICATION":
        raise ValueError("procedure must be completed before a repair attempt can be staged")
    if procedure_session.get("procedure_id") != gate.get("procedure_id"):
        raise ValueError("procedure session does not match repair gate")
    if verify_procedure_receipts(procedure_session).get("status") != "PASS":
        raise ValueError("procedure receipt chain failed verification")
    actors = {str(v) for v in actor_role_ids if v}
    if not actors:
        raise PermissionError("at least one actor role is required to stage a repair attempt")
    session_actors = {str(v) for v in procedure_session.get("actor_role_ids", []) if v}
    if session_actors and not actors.intersection(session_actors):
        raise PermissionError("staging actor does not participate in the completed procedure session")
    required = {"plan_id", "source_ref", "target_system_id", "planned_action_summary", "reversibility"}
    missing = sorted(required - set(repair_plan_receipt))
    if missing:
        raise ValueError("repair plan receipt missing: " + ", ".join(missing))
    if str(repair_plan_receipt.get("target_system_id")) != str(gate.get("source_system_id")):
        raise ValueError("repair plan target system does not match gate")
    if repair_plan_receipt.get("consumes_spares") and not repair_plan_receipt.get("spare_verification_receipt_id"):
        raise ValueError("spare consumption requires an explicit spare verification receipt")
    if repair_plan_receipt.get("fabricated_part") and not repair_plan_receipt.get("part_validation_receipt_id"):
        raise ValueError("fabricated repair part requires an explicit validation receipt")

    packet = {
        "schema": "axm.repair-attempt.v1",
        "version": REPAIR_VERIFICATION_VERSION,
        "gate_id": gate["gate_id"],
        "gate_hash": gate["gate_hash"],
        "source_failure_id": gate["source_failure_id"],
        "source_system_id": gate.get("source_system_id"),
        "procedure_id": gate.get("procedure_id"),
        "procedure_session_id": procedure_session.get("session_id"),
        "procedure_ledger_head": procedure_session.get("previous_receipt_hash"),
        "actor_role_ids": sorted(set(str(v) for v in actor_role_ids)),
        "repair_plan_receipt": copy.deepcopy(repair_plan_receipt),
        "status": "STAGED_AWAIT_EXTERNAL_EXECUTION",
        "authority": "record_and_verify_only",
        "may_execute_repair": False,
        "may_modify_runtime": False,
        "may_clear_fault": False,
        "fault_cleared": False,
        "repair_verified": False,
        "verification_complete": False,
        "fault_clearance_eligible": False,
        "receipts": [],
        "previous_receipt_hash": None,
    }
    packet["attempt_id"] = _hash({
        "gate_hash": packet["gate_hash"],
        "procedure_session_id": packet["procedure_session_id"],
        "repair_plan_receipt": packet["repair_plan_receipt"],
        "actor_role_ids": packet["actor_role_ids"],
    }, "AXM-REPAIR-ATTEMPT-ID-V1")
    return packet

def _append_receipt(attempt: dict[str, Any], receipt_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    current = copy.deepcopy(attempt)
    receipt = {
        "schema": "axm.repair-attempt-receipt.v1",
        "receipt_type": receipt_type,
        "attempt_id": current["attempt_id"],
        "payload": copy.deepcopy(payload),
        "previous_receipt_hash": current.get("previous_receipt_hash"),
        "fault_cleared": False,
        "may_modify_runtime": False,
        "may_clear_fault": False,
    }
    receipt["receipt_hash"] = _hash(receipt, "AXM-REPAIR-ATTEMPT-RECEIPT-V1")
    current["receipts"].append(receipt)
    current["previous_receipt_hash"] = receipt["receipt_hash"]
    return current

def record_external_repair_execution(
    attempt: dict[str, Any],
    execution_receipt: dict[str, Any],
) -> dict[str, Any]:
    if attempt.get("status") != "STAGED_AWAIT_EXTERNAL_EXECUTION":
        raise ValueError("repair attempt is not awaiting external execution")
    required = {"execution_id", "executor_ref", "result_claim", "evidence_ids"}
    missing = sorted(required - set(execution_receipt))
    if missing:
        raise ValueError("execution receipt missing: " + ", ".join(missing))
    if not isinstance(execution_receipt.get("evidence_ids"), list) or not execution_receipt["evidence_ids"]:
        raise ValueError("execution receipt requires at least one evidence id")
    current = _append_receipt(attempt, "external_execution", execution_receipt)
    current["status"] = "ATTEMPT_RECORDED_AWAIT_POST_REPAIR_VERIFICATION"
    current["external_result_claim"] = execution_receipt.get("result_claim")
    current["fault_cleared"] = False
    current["repair_verified"] = False
    current["verification_complete"] = False
    current["fault_clearance_eligible"] = False
    return current

def assess_post_repair_verification(
    attempt: dict[str, Any],
    verification_receipt: dict[str, Any],
) -> dict[str, Any]:
    if attempt.get("status") != "ATTEMPT_RECORDED_AWAIT_POST_REPAIR_VERIFICATION":
        raise ValueError("repair attempt is not awaiting post-repair verification")
    required = {
        "verification_id",
        "source_ref",
        "evidence_ids",
        "independent_check_ids",
        "outcome",
        "observed_fault_absent",
        "system_function_restored",
    }
    missing = sorted(required - set(verification_receipt))
    if missing:
        raise ValueError("verification receipt missing: " + ", ".join(missing))
    outcome = str(verification_receipt.get("outcome"))
    if outcome not in {"effective", "not_effective", "inconclusive"}:
        raise ValueError("unsupported verification outcome")
    evidence = verification_receipt.get("evidence_ids")
    checks = verification_receipt.get("independent_check_ids")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("post-repair verification requires evidence")
    if not isinstance(checks, list):
        raise ValueError("independent_check_ids must be a list")

    effective_claim_supported = (
        outcome == "effective"
        and bool(verification_receipt.get("observed_fault_absent"))
        and bool(verification_receipt.get("system_function_restored"))
        and len(checks) > 0
    )
    normalized_outcome = outcome
    if outcome == "effective" and not effective_claim_supported:
        normalized_outcome = "inconclusive"

    current = _append_receipt(attempt, "post_repair_verification", {
        **copy.deepcopy(verification_receipt),
        "normalized_outcome": normalized_outcome,
    })
    current["verification_complete"] = normalized_outcome in {"effective", "not_effective"}
    current["repair_verified"] = normalized_outcome == "effective"
    current["fault_clearance_eligible"] = normalized_outcome == "effective"
    current["fault_cleared"] = False
    current["verification_outcome"] = normalized_outcome
    current["status"] = {
        "effective": "VERIFIED_EFFECTIVE_CLEARANCE_ELIGIBLE",
        "not_effective": "VERIFIED_NOT_EFFECTIVE_FAULT_REMAINS",
        "inconclusive": "VERIFICATION_INCONCLUSIVE_FAULT_REMAINS",
    }[normalized_outcome]
    return current

def build_fault_clearance_candidate(attempt: dict[str, Any]) -> dict[str, Any]:
    if attempt.get("status") != "VERIFIED_EFFECTIVE_CLEARANCE_ELIGIBLE":
        raise ValueError("repair attempt is not eligible for a fault-clearance candidate")
    packet = {
        "schema": "axm.fault-clearance-candidate.v1",
        "version": REPAIR_VERIFICATION_VERSION,
        "attempt_id": attempt.get("attempt_id"),
        "source_failure_id": attempt.get("source_failure_id"),
        "source_system_id": attempt.get("source_system_id"),
        "verification_receipt_hash": attempt.get("previous_receipt_hash"),
        "status": "CLEARANCE_CANDIDATE_REQUIRES_AUTHORITATIVE_APPLY",
        "fault_clearance_eligible": True,
        "fault_cleared": False,
        "authority": "eligibility_only",
        "may_modify_runtime": False,
        "may_clear_fault": False,
    }
    packet["candidate_hash"] = _hash(packet, "AXM-FAULT-CLEARANCE-CANDIDATE-V1")
    return packet

def verify_repair_attempt_receipts(attempt: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    previous = None
    for index, receipt in enumerate(attempt.get("receipts", [])):
        if receipt.get("previous_receipt_hash") != previous:
            failures.append(f"receipt[{index}] previous hash mismatch")
        raw = copy.deepcopy(receipt)
        claimed = raw.pop("receipt_hash", None)
        expected = _hash(raw, "AXM-REPAIR-ATTEMPT-RECEIPT-V1")
        if claimed != expected:
            failures.append(f"receipt[{index}] hash mismatch")
        previous = claimed
    if attempt.get("receipts") and attempt.get("previous_receipt_hash") != previous:
        failures.append("attempt ledger head mismatch")
    return {
        "schema": "axm.repair-attempt-chain-verification.v1",
        "status": "PASS" if not failures else "FAIL",
        "receipt_count": len(attempt.get("receipts", [])),
        "failures": failures,
    }
