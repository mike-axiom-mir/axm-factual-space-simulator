from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

REHEARSAL_VERSION = "0.4.0-candidate"

ROLE_PLANS = {
    "instrument": ("science", "engineering", "navigation", "command"),
    "patient_observation": ("navigation", "science", "command"),
    "general": ("command", "engineering", "navigation"),
}

def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def _hash(value: Any, domain: str) -> str:
    return hashlib.sha256(f"{domain}|{_canonical(value)}".encode("utf-8")).hexdigest()

def _flags(action: dict[str, Any]) -> list[str]:
    text = " ".join(str(action.get(key, "")).lower() for key in ("source_thread", "intent", "label", "category"))
    flags: list[str] = []
    if "communication" in text or "light" in text or "delayed" in text:
        flags.append("light_time_sensitive")
    if "radiation" in text or "shield" in text:
        flags.append("radiation_sensitive")
    if any(token in text for token in ("hypoth", "detect", "signal", "sensor", "spectral", "coupling", "calibration")):
        flags.append("evidence_discrimination")
    return flags

def build_action_rehearsal(action: dict[str, Any], *, index: int = 0) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise TypeError("action must be an object")
    action_id = str(action.get("action_id") or "")
    if not action_id:
        raise ValueError("action_id is required")
    category = str(action.get("category") or "general")
    roles = ROLE_PLANS.get(category, ROLE_PLANS["general"])
    primary = roles[0]
    steps = [
        {"step_id":"review-source-intent","title":"Review source intent","station_role":primary,"required_evidence":["source_action_intent"],"hold_point":False,"completion_semantics":"evidence_review_only","may_execute_action":False,"may_modify_runtime":False},
        {"step_id":"check-live-constraints","title":"Check current constraints","station_role":roles[min(1,len(roles)-1)],"required_evidence":["read_only_runtime_constraints"],"hold_point":True,"completion_semantics":"hold_acknowledged_only","may_execute_action":False,"may_modify_runtime":False},
        {"step_id":"prepare-relevant-stations","title":"Prepare relevant stations","station_role":roles[min(2,len(roles)-1)],"required_evidence":["station_readiness_receipt"],"hold_point":False,"completion_semantics":"rehearsal_readiness_only","may_execute_action":False,"may_modify_runtime":False},
        {"step_id":"request-command-authority","title":"Request command authority","station_role":"command","required_evidence":["command_authority_receipt"],"hold_point":True,"completion_semantics":"request_only_not_execution","may_execute_action":False,"may_modify_runtime":False},
    ]
    packet = {
        "schema":"axm.bridge-action-rehearsal.v1","version":REHEARSAL_VERSION,"rehearsal_id":f"rehearsal:{action_id}","source_action_index":index,"source_action_id":action_id,"source_action_label":action.get("label"),"source_thread":action.get("source_thread"),"category":category,"intent":action.get("intent"),"priority":action.get("priority"),"station_order":list(roles),"primary_station":primary,"context_flags":_flags(action),"steps":steps,"status":"PLANNING_REHEARSAL_ONLY","authority":"presentation_rehearsal_only","may_execute_action":False,"may_advance_mission_time":False,"may_append_event":False,"may_retarget_event":False,"may_modify_runtime":False,"may_close_thread":False,"may_change_truth_labels":False,
    }
    packet["rehearsal_hash"] = _hash(packet, "AXM-BRIDGE-ACTION-REHEARSAL-V1")
    return packet

def build_rehearsal_catalog(operations_context: dict[str, Any]) -> dict[str, Any]:
    if operations_context.get("schema") != "axm.living-operations-context.v1":
        raise ValueError("unsupported operations context")
    actions = operations_context.get("actions", [])
    if not isinstance(actions, list):
        raise ValueError("operations actions must be a list")
    rehearsals = [build_action_rehearsal(copy.deepcopy(action), index=index) for index, action in enumerate(actions) if isinstance(action, dict) and action.get("action_id")]
    packet = {"schema":"axm.bridge-rehearsal-catalog.v1","version":REHEARSAL_VERSION,"source_context_hash":operations_context.get("context_hash"),"rehearsal_count":len(rehearsals),"rehearsals":rehearsals,"selection_authority":"user_inspect_only","completion_boundary":"rehearsal_never_executes_source_action","may_execute_action":False,"may_modify_runtime":False,"may_close_thread":False,"may_change_truth_labels":False}
    packet["catalog_hash"] = _hash(packet, "AXM-BRIDGE-REHEARSAL-CATALOG-V1")
    return packet
