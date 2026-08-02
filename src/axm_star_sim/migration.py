from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PACKAGE_ROOT / "data"


class MigrationError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def domain_hash(value: Any, domain: str) -> str:
    return hashlib.sha256(f"{domain}|{canonical_json(value)}".encode("utf-8")).hexdigest()


def load_migration_policy() -> dict[str, Any]:
    return json.loads((DATA_DIR / "save_migration_policy_registry.json").read_text(encoding="utf-8"))


def default_policy() -> dict[str, Any]:
    registry = load_migration_policy()
    return next(row for row in registry["policies"] if row["id"] == registry["default_policy_id"])


def create_migration_proposal(
    start_pin: dict[str, Any],
    migration_type: str,
    requested_changes: dict[str, Any],
    evidence_receipts: list[str] | None = None,
    rollback_plan: str = "retain original save and write a derived representation",
) -> dict[str, Any]:
    policy = default_policy()
    if migration_type not in policy["allowed_migration_types"]:
        raise MigrationError(f"unsupported migration type: {migration_type}")
    proposal = {
        "schema": "axm.save-migration-proposal.v1",
        "policy_id": policy["id"],
        "migration_type": migration_type,
        "source_pin": copy.deepcopy(start_pin),
        "requested_changes": copy.deepcopy(requested_changes),
        "evidence_receipts": list(evidence_receipts or []),
        "rollback_plan": rollback_plan,
    }
    proposal["proposal_receipt"] = domain_hash(proposal, "AXM-SAVE-MIGRATION-PROPOSAL-V1")
    return proposal


def assess_migration_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    policy = default_policy()
    failures: list[str] = []
    holds: list[str] = []
    if proposal.get("policy_id") != policy["id"]:
        failures.append("wrong migration policy")
    if proposal.get("migration_type") not in policy["allowed_migration_types"]:
        failures.append("migration type is not allowed")
    expected = copy.deepcopy(proposal)
    supplied = expected.pop("proposal_receipt", None)
    if supplied != domain_hash(expected, "AXM-SAVE-MIGRATION-PROPOSAL-V1"):
        failures.append("proposal receipt mismatch")
    source_pin = proposal.get("source_pin", {})
    changes = proposal.get("requested_changes", {})
    for field in policy["pinned_fields"]:
        if field in changes and changes[field] != source_pin.get(field):
            failures.append(f"pinned field change attempted: {field}")
    forbidden_tokens = (
        "rewrite_history", "replace_roots", "change_seed", "raise_claim_without_evidence",
        "replace_hidden_scenario", "invent_capability", "silently_change_semantics"
    )
    if any(bool(changes.get(token)) for token in forbidden_tokens):
        failures.append("explicit forbidden change requested")
    if not proposal.get("rollback_plan"):
        holds.append("rollback plan missing")
    if proposal.get("migration_type") == "explicit_fork" and not changes.get("new_branch_id"):
        holds.append("explicit fork requires a new branch id")
    verdict = "REJECT" if failures else "HOLD" if holds else "ACCEPT"
    result = {
        "schema": "axm.save-migration-assessment.v1",
        "policy_id": policy["id"],
        "verdict": verdict,
        "failures": failures,
        "holds": holds,
        "source_pin_preserved": not any("pinned field" in item for item in failures),
        "rule": "Compatibility may be added around a save; its historical identity may not be silently rewritten.",
    }
    result["assessment_receipt"] = domain_hash(result, "AXM-SAVE-MIGRATION-ASSESSMENT-V1")
    return result


def create_visual_reconstruction_packet(
    start_pin: dict[str, Any],
    historical_state_hash: str,
    target_render_profile_id: str,
    target_render_profile_version: int,
) -> dict[str, Any]:
    packet = {
        "schema": "axm.visual-reconstruction-migration.v1",
        "original_start_pin": copy.deepcopy(start_pin),
        "historical_state_hash": historical_state_hash,
        "target_render_profile_id": target_render_profile_id,
        "target_render_profile_version": target_render_profile_version,
        "semantic_change_allowed": False,
        "historical_rewrite_allowed": False,
    }
    packet["reconstruction_receipt"] = domain_hash(packet, "AXM-VISUAL-RECONSTRUCTION-MIGRATION-V1")
    return packet
