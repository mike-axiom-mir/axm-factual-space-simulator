from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

PROCEDURE_VERSION = "0.5.0-candidate"

SYSTEM_ROUTE_MAP = {
    "electrical_power_generation": ("engineering_station", "vehicle_systems_engineer"),
    "energy_storage": ("engineering_station", "vehicle_systems_engineer"),
    "power_distribution": ("engineering_station", "vehicle_systems_engineer"),
    "thermal_control": ("engineering_station", "vehicle_systems_engineer"),
    "primary_structure": ("engineering_station", "vehicle_systems_engineer"),
    "eclss_atmosphere": ("engineering_station", "vehicle_systems_engineer"),
    "water_and_waste": ("engineering_station", "vehicle_systems_engineer"),
    "fire_and_emergency_response": ("engineering_station", "vehicle_systems_engineer"),
    "avionics_cdh": ("engineering_station", "vehicle_systems_engineer"),
    "docking_airlock_eva": ("engineering_station", "vehicle_systems_engineer"),
    "mmod_and_external_protection": ("engineering_station", "vehicle_systems_engineer"),
    "gnc": ("navigation_station", "flight_dynamics_navigation"),
    "reaction_control": ("navigation_station", "flight_dynamics_navigation"),
    "main_propulsion": ("navigation_station", "flight_dynamics_navigation"),
    "communications": ("communications_station", "communications_data_robotics"),
    "robotics_and_probe_operations": ("communications_station", "communications_data_robotics"),
    "radiation_monitoring_and_shelter": ("command_duet", "mission_commander"),
    "crew_health_medical": ("medical_station", "crew_medical_officer"),
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any, domain: str) -> str:
    return hashlib.sha256(f"{domain}|{_canonical(value)}".encode("utf-8")).hexdigest()


def _station_roles(station_registry: dict[str, Any]) -> dict[str, set[str]]:
    stations = station_registry.get("stations", []) if isinstance(station_registry, dict) else []
    out: dict[str, set[str]] = {}
    for row in stations:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        out[str(row["id"])] = {str(v) for v in row.get("seat_role_ids", []) if v}
    return out


def _route_for_failure(failure: dict[str, Any], station_registry: dict[str, Any]) -> tuple[str, str]:
    system_id = str(failure.get("system_id") or "")
    station_id, role_id = SYSTEM_ROUTE_MAP.get(system_id, ("command_duet", "mission_commander"))
    known = _station_roles(station_registry)
    if station_id not in known:
        raise ValueError(f"mapped station is absent from station registry: {station_id}")
    if role_id not in known[station_id]:
        raise ValueError(f"mapped role {role_id} is absent from station {station_id}")
    return station_id, role_id


def build_failure_procedure(failure: dict[str, Any], station_registry: dict[str, Any], *, index: int = 0) -> dict[str, Any]:
    if not isinstance(failure, dict):
        raise TypeError("failure must be an object")
    failure_id = str(failure.get("id") or "")
    if not failure_id:
        raise ValueError("failure id is required")
    station_id, role_id = _route_for_failure(failure, station_registry)
    detections = [str(v) for v in failure.get("detection", []) if v]
    responses = [str(v) for v in failure.get("automatic_response", []) if v]
    command_level = str(failure.get("command_level") or "unknown")
    criticality = str(failure.get("criticality") or "unknown")

    if failure_id == "crew_medical_event":
        packet = {
            "schema":"axm.failure-procedure-definition.v1","version":PROCEDURE_VERSION,
            "procedure_id":f"failure-procedure:{failure_id}:v1","source_failure_index":index,
            "source_failure_id":failure_id,"source_system_id":failure.get("system_id"),
            "source_criticality":criticality,"source_command_level":command_level,
            "primary_station_id":station_id,"primary_role_id":role_id,
            "detection_signal_ids":detections,"source_declared_automatic_response_ids":responses,
            "status":"HOLD_SPECIALIST_MEDICAL_PROCEDURE_REQUIRED","steps":[],
            "truth_boundary":"No generic medical procedure is synthesized by this candidate.",
            "authority":"routing_and_hold_only","may_execute_response":False,"may_modify_runtime":False,
            "may_clear_fault":False,"may_claim_repair_success":False,
        }
        packet["procedure_hash"] = _hash(packet, "AXM-FAILURE-PROCEDURE-DEFINITION-V1")
        return packet

    steps = [
        {"step_id":"confirm-detection-evidence","title":"Confirm detection evidence","station_id":station_id,
         "authorized_role_ids":[role_id,"mission_commander"],"required_evidence_ids":detections or ["declared_detection_evidence"],
         "hold_point":True,"completion_semantics":"evidence_review_only","may_execute_response":False,"may_modify_runtime":False,"may_clear_fault":False},
        {"step_id":"review-source-declared-responses","title":"Review source-declared automatic responses","station_id":station_id,
         "authorized_role_ids":[role_id,"mission_commander"],"required_evidence_ids":["automatic_response_receipt"],
         "source_declared_response_ids":responses,"hold_point":False,"completion_semantics":"response_receipt_review_only","may_execute_response":False,"may_modify_runtime":False,"may_clear_fault":False},
        {"step_id":"inspect-current-consequences","title":"Inspect current consequences and remaining uncertainty","station_id":station_id,
         "authorized_role_ids":[role_id,"mission_commander"],"required_evidence_ids":["read_only_runtime_snapshot","fault_effect_snapshot"],
         "hold_point":criticality in {"high","crew_survival"},"completion_semantics":"state_assessment_only","may_execute_response":False,"may_modify_runtime":False,"may_clear_fault":False},
    ]
    if command_level == "command_required":
        steps.append({"step_id":"request-command-authority","title":"Request command authority","station_id":"command_duet",
                      "authorized_role_ids":["mission_commander"],"required_evidence_ids":["command_authority_receipt"],
                      "hold_point":True,"completion_semantics":"request_only_not_execution","may_execute_response":False,"may_modify_runtime":False,"may_clear_fault":False})
    else:
        steps.append({"step_id":"record-advisory-disposition","title":"Record advisory disposition","station_id":station_id,
                      "authorized_role_ids":[role_id,"mission_commander"],"required_evidence_ids":["advisory_disposition_receipt"],
                      "hold_point":False,"completion_semantics":"record_only_not_execution","may_execute_response":False,"may_modify_runtime":False,"may_clear_fault":False})

    packet = {
        "schema":"axm.failure-procedure-definition.v1","version":PROCEDURE_VERSION,
        "procedure_id":f"failure-procedure:{failure_id}:v1","source_failure_index":index,
        "source_failure_id":failure_id,"source_system_id":failure.get("system_id"),
        "source_criticality":criticality,"source_command_level":command_level,
        "primary_station_id":station_id,"primary_role_id":role_id,
        "detection_signal_ids":detections,"source_declared_automatic_response_ids":responses,
        "status":"PROCEDURE_AVAILABLE_FOR_REVIEW","steps":steps,
        "completion_boundary":"PROCEDURE_COMPLETE_AWAIT_EXTERNAL_OUTCOME_VERIFICATION",
        "authority":"procedure_guidance_only","may_execute_response":False,"may_modify_runtime":False,
        "may_clear_fault":False,"may_claim_repair_success":False,
    }
    packet["procedure_hash"] = _hash(packet, "AXM-FAILURE-PROCEDURE-DEFINITION-V1")
    return packet


def build_failure_procedure_catalog(failure_registry: dict[str, Any], station_registry: dict[str, Any]) -> dict[str, Any]:
    if failure_registry.get("schema") != "axm.ship-failure-mode-registry.v1":
        raise ValueError("unsupported failure registry")
    if station_registry.get("schema") != "axm.crew-station-display-registry.v1":
        raise ValueError("unsupported station registry")
    failures = failure_registry.get("failure_modes", [])
    if not isinstance(failures, list):
        raise ValueError("failure_modes must be a list")
    procedures = [build_failure_procedure(copy.deepcopy(row), station_registry, index=index) for index, row in enumerate(failures) if isinstance(row, dict)]
    packet = {"schema":"axm.failure-procedure-catalog.v1","version":PROCEDURE_VERSION,
              "source_failure_registry_version":failure_registry.get("registry_version"),
              "source_station_registry_version":station_registry.get("registry_version"),
              "procedure_count":len(procedures),"procedures":procedures,"authority":"review_and_training_only",
              "may_execute_response":False,"may_modify_runtime":False,"may_clear_fault":False,"may_claim_repair_success":False}
    packet["catalog_hash"] = _hash(packet, "AXM-FAILURE-PROCEDURE-CATALOG-V1")
    return packet


def start_procedure_session(procedure: dict[str, Any], *, actor_role_ids: list[str], trigger_receipt: dict[str, Any]) -> dict[str, Any]:
    if procedure.get("status") != "PROCEDURE_AVAILABLE_FOR_REVIEW":
        raise ValueError("procedure is on HOLD and cannot start")
    steps = procedure.get("steps", [])
    if not steps:
        raise ValueError("procedure has no executable review steps")
    allowed = set(steps[0].get("authorized_role_ids", []))
    if allowed and not allowed.intersection(actor_role_ids):
        raise PermissionError("actor role is not authorized to start this procedure")
    packet = {"schema":"axm.failure-procedure-session.v1","version":PROCEDURE_VERSION,
              "procedure_id":procedure["procedure_id"],"procedure_hash":procedure["procedure_hash"],
              "source_failure_id":procedure["source_failure_id"],"actor_role_ids":sorted(set(actor_role_ids)),
              "trigger_receipt":copy.deepcopy(trigger_receipt),"status":"ACTIVE_REVIEW","current_step_index":0,
              "step_receipts":[],"previous_receipt_hash":None,"fault_cleared":False,"repair_verified":False,
              "may_execute_response":False,"may_modify_runtime":False}
    packet["session_id"] = _hash({"procedure_hash":packet["procedure_hash"],"actor_role_ids":packet["actor_role_ids"],"trigger_receipt":packet["trigger_receipt"]}, "AXM-FAILURE-PROCEDURE-SESSION-ID-V1")
    return packet


def submit_procedure_step(procedure: dict[str, Any], session: dict[str, Any], *, actor_role_ids: list[str], evidence_ids: list[str], hold_acknowledged: bool = False) -> dict[str, Any]:
    current = copy.deepcopy(session)
    if current.get("status") != "ACTIVE_REVIEW":
        raise ValueError("procedure session is not active")
    if procedure.get("procedure_hash") != current.get("procedure_hash"):
        raise ValueError("procedure definition changed; session remains pinned")
    steps = procedure.get("steps", [])
    index = int(current.get("current_step_index", 0))
    if index < 0 or index >= len(steps):
        raise ValueError("procedure step index out of range")
    step = steps[index]
    authorized = set(step.get("authorized_role_ids", []))
    if authorized and not authorized.intersection(actor_role_ids):
        raise PermissionError("actor role is not authorized for this procedure step")
    supplied = {str(v) for v in evidence_ids}
    required = {str(v) for v in step.get("required_evidence_ids", [])}
    reasons = []
    missing = sorted(required - supplied)
    if missing:
        reasons.append("missing required evidence: " + ", ".join(missing))
    if step.get("hold_point") and not hold_acknowledged:
        reasons.append("explicit hold acknowledgement required")
    if reasons:
        current["status"] = "HOLD"
        current["hold"] = {"step_id":step["step_id"],"reasons":reasons,"authority":"no_advance"}
        return current
    receipt = {"schema":"axm.failure-procedure-step-receipt.v1","procedure_id":procedure["procedure_id"],
               "procedure_hash":procedure["procedure_hash"],"session_id":current["session_id"],"step_id":step["step_id"],
               "step_index":index,"actor_role_ids":sorted(set(actor_role_ids)),"evidence_ids":sorted(supplied),
               "hold_acknowledged":bool(hold_acknowledged),"completion_semantics":step["completion_semantics"],
               "previous_receipt_hash":current.get("previous_receipt_hash"),"fault_cleared":False,"repair_verified":False,
               "may_execute_response":False,"may_modify_runtime":False}
    receipt["receipt_hash"] = _hash(receipt, "AXM-FAILURE-PROCEDURE-STEP-RECEIPT-V1")
    current["step_receipts"].append(receipt)
    current["previous_receipt_hash"] = receipt["receipt_hash"]
    current.pop("hold", None)
    next_index = index + 1
    if next_index >= len(steps):
        current["status"] = "PROCEDURE_COMPLETE_AWAIT_EXTERNAL_OUTCOME_VERIFICATION"
        current["current_step_index"] = len(steps) - 1
        current["fault_cleared"] = False
        current["repair_verified"] = False
    else:
        current["status"] = "ACTIVE_REVIEW"
        current["current_step_index"] = next_index
    return current


def resume_held_session(session: dict[str, Any]) -> dict[str, Any]:
    current = copy.deepcopy(session)
    if current.get("status") == "HOLD":
        current["status"] = "ACTIVE_REVIEW"
        current.pop("hold", None)
    return current


def verify_procedure_receipts(session: dict[str, Any]) -> dict[str, Any]:
    failures = []
    previous = None
    for index, receipt in enumerate(session.get("step_receipts", [])):
        if receipt.get("previous_receipt_hash") != previous:
            failures.append(f"receipt[{index}] previous hash mismatch")
        raw = copy.deepcopy(receipt)
        claimed = raw.pop("receipt_hash", None)
        expected = _hash(raw, "AXM-FAILURE-PROCEDURE-STEP-RECEIPT-V1")
        if claimed != expected:
            failures.append(f"receipt[{index}] hash mismatch")
        previous = claimed
    if session.get("step_receipts") and session.get("previous_receipt_hash") != previous:
        failures.append("session ledger head mismatch")
    return {"schema":"axm.failure-procedure-chain-verification.v1","status":"PASS" if not failures else "FAIL","receipt_count":len(session.get("step_receipts", [])),"failures":failures}
