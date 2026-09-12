import copy
import unittest

from axm_star_sim import ship_blueprint as ship
from axm_star_sim.post_clearance_recovery import (
    RECOVERY_AUTHORITY_POLICY_ID,
    _hash,
    apply_safe_state_exit,
    build_post_clearance_recovery_contract,
    build_post_clearance_recovery_contract_catalog,
    build_recovery_assessment,
    build_safe_state_exit_authorization,
    verify_recovery_chain,
)


def clearance_receipt(state, *, failure_id="co2_removal_degraded", system_id="eclss_atmosphere", candidate_hash="candidate-clear-1"):
    receipt = {
        "schema": "axm.fault-clearance-apply-receipt.v1",
        "version": "0.8.0-candidate",
        "status": "APPLIED_VERIFIED_FAULT_CLEARANCE",
        "failure_mode_id": failure_id,
        "system_id": system_id,
        "candidate_hash": candidate_hash,
        "repair_attempt_id": "repair-attempt-1",
        "state_hash_before": "pre-clearance-state",
        "state_hash_after": state["state_hash"],
        "authorization_receipt_hash": "clearance-auth",
        "reconciliation_receipt_hash": "reconciliation",
        "reconciled_paths": [f"system_health.{system_id}.mode"],
        "pending_recall_cleared": True,
        "pending_recall_retargeted_to": None,
        "fault_cleared": True,
        "repair_verified": True,
        "may_clear_unrelated_faults": False,
        "safe_state_exit_automatic": False,
        "authority_policy_id": "axm.fault-clearance-authority-policy.candidate.v1",
    }
    receipt["apply_receipt_hash"] = _hash(receipt, "AXM-FAULT-CLEARANCE-APPLY-RECEIPT-V1")
    return receipt


def post_clearance_safe_state():
    state = ship.create_ship_state("v0.10-recovery-test")
    state["mode"] = "safe_state"
    if "science_payload_and_analysis" not in state["power"]["shed_loads"]:
        state["power"]["shed_loads"].append("science_payload_and_analysis")
    ship._append_fault(state, {
        "record_type": "verified_clearance",
        "failure_mode_id": "co2_removal_degraded",
        "system_id": "eclss_atmosphere",
        "candidate_hash": "candidate-clear-1",
        "repair_attempt_id": "repair-attempt-1",
        "repair_verification_receipt_hash": "verification",
        "authorization_receipt_hash": "clearance-auth",
        "reconciliation_receipt_hash": "reconciliation",
        "reconciled_paths": ["system_health.eclss_atmosphere.mode"],
        "pending_recall_cleared": True,
        "pending_recall_retargeted_to": None,
        "fault_cleared": True,
        "repair_verified": True,
        "clearance_semantics": "verified_effective_repair_plus_exact_observed_state_reconciliation",
    })
    state["state_hash"] = ship.state_hash(state)
    return state


class PostClearanceRecoveryTests(unittest.TestCase):
    def assessment(self, state=None):
        state = state or post_clearance_safe_state()
        receipt = clearance_receipt(state)
        assessment = build_recovery_assessment(
            state,
            receipt,
            source_ref="post-clearance-instrument-sweep",
            evidence_ids=["life-support-panel", "power-panel"],
            independent_check_ids=["mission-control-crosscheck"],
        )
        return state, receipt, assessment

    def test_contract_keeps_recovery_authority_explicit_and_non_canon(self):
        clearance = {
            "schema": "axm.fault-clearance-apply-contract.v1",
            "status": "ENGINE_AVAILABLE_REQUIRES_VERIFIED_CANDIDATE_AND_LIVE_SHIP_STATE",
            "source_failure_id": "co2_removal_degraded",
            "source_system_id": "eclss_atmosphere",
            "contract_id": "clearance-apply:co2_removal_degraded:v1",
            "contract_hash": "clearance-contract",
        }
        contract = build_post_clearance_recovery_contract(clearance)
        self.assertEqual(contract["status"], "RECOVERY_ENGINE_AVAILABLE_AFTER_APPLIED_VERIFIED_CLEARANCE")
        self.assertEqual(contract["candidate_authority_policy"]["truth_status"], "simulation_policy_candidate_not_canon")
        self.assertFalse(contract["may_exit_safe_state_automatically"])
        self.assertFalse(contract["may_restore_resources"])
        catalog = build_post_clearance_recovery_contract_catalog({
            "schema": "axm.fault-clearance-apply-contract-catalog.v1",
            "contracts": [clearance],
        })
        self.assertEqual(catalog["contract_count"], 1)
        self.assertFalse(catalog["may_modify_presentation_runtime"])

    def test_fault_clearance_and_full_recovery_are_distinct(self):
        state, receipt, assessment = self.assessment()
        self.assertEqual(state["mode"], "safe_state")
        self.assertEqual(assessment["status"], "DEGRADED_SAFE_RECOVERY_RELEASE_ELIGIBLE")
        self.assertTrue(assessment["fault_cleared_does_not_imply_full_recovery"])
        self.assertIn("load_sheds_remain", assessment["residual_state_snapshot"]["residual_indicators"])
        self.assertTrue(assessment["safe_state_exit_eligible"])
        self.assertFalse(receipt["safe_state_exit_automatic"])

    def test_commander_authorization_is_required(self):
        _, _, assessment = self.assessment()
        with self.assertRaises(PermissionError):
            build_safe_state_exit_authorization(
                assessment,
                source_ref="release-board",
                actor_role_ids=["vehicle_systems_engineer"],
                evidence_ids=["release-check"],
            )
        auth = build_safe_state_exit_authorization(
            assessment,
            source_ref="release-board",
            actor_role_ids=["mission_commander", "vehicle_systems_engineer"],
            evidence_ids=["release-check"],
        )
        self.assertEqual(auth["authority_policy_id"], RECOVERY_AUTHORITY_POLICY_ID)

    def test_release_changes_mode_only_and_preserves_residuals(self):
        state, receipt, assessment = self.assessment()
        auth = build_safe_state_exit_authorization(
            assessment,
            source_ref="release-board",
            actor_role_ids=["mission_commander"],
            evidence_ids=["release-check"],
        )
        before = copy.deepcopy(state)
        updated, apply_receipt = apply_safe_state_exit(
            state,
            clearance_apply_receipt=receipt,
            assessment=assessment,
            authorization_receipt=auth,
        )
        self.assertEqual(updated["mode"], "nominal")
        self.assertEqual(updated["power"]["shed_loads"], before["power"]["shed_loads"])
        self.assertEqual(updated["power"]["battery_energy_kwh"], before["power"]["battery_energy_kwh"])
        self.assertEqual(updated["water"], before["water"])
        self.assertEqual(updated["crew"], before["crew"])
        self.assertEqual(updated["structure"], before["structure"])
        self.assertEqual(updated["system_health"], before["system_health"])
        self.assertEqual(updated["fault_ledger"], before["fault_ledger"])
        self.assertFalse(apply_receipt["resource_values_restored"])
        self.assertFalse(apply_receipt["load_sheds_removed_by_exit"])
        self.assertTrue(apply_receipt["residual_state_preserved"])
        self.assertTrue(ship.verify_ship_state(updated)["valid"])

    def test_stale_state_requires_fresh_assessment(self):
        state, receipt, assessment = self.assessment()
        auth = build_safe_state_exit_authorization(
            assessment,
            source_ref="release-board",
            actor_role_ids=["mission_commander"],
            evidence_ids=["release-check"],
        )
        drifted = copy.deepcopy(state)
        drifted["communications"]["data_queue_gb"] += 0.25
        drifted["state_hash"] = ship.state_hash(drifted)
        result = verify_recovery_chain(drifted, receipt, assessment, auth)
        self.assertEqual(result["status"], "FAIL")

    def test_command_required_fault_blocks_release(self):
        state, receipt, _ = self.assessment()
        faulted = ship.apply_failure_mode(state, "battery_low_state_of_charge")
        assessment = build_recovery_assessment(
            faulted,
            receipt,
            source_ref="post-clearance-instrument-sweep",
            evidence_ids=["life-support-panel"],
            independent_check_ids=["mission-control-crosscheck"],
        )
        self.assertFalse(assessment["safe_state_exit_eligible"])
        self.assertIn("blocking_active_faults_remain", assessment["release_blockers"])
        self.assertIn("command_recall_remains", assessment["release_blockers"])

    def test_rehashed_assessment_cannot_lie_about_release_status(self):
        state, receipt, assessment = self.assessment()
        forged = copy.deepcopy(assessment)
        forged["status"] = "NOMINAL_RECOVERY_RELEASE_ELIGIBLE"
        raw = copy.deepcopy(forged)
        raw.pop("assessment_hash")
        forged["assessment_hash"] = _hash(raw, "AXM-POST-CLEARANCE-RECOVERY-ASSESSMENT-V1")
        self.assertEqual(verify_recovery_chain(state, receipt, forged)["status"], "FAIL")

    def test_authorization_cannot_be_substituted_between_assessments(self):
        state, receipt, first = self.assessment()
        second = build_recovery_assessment(
            state,
            receipt,
            source_ref="second-instrument-sweep",
            evidence_ids=["life-support-panel", "power-panel"],
            independent_check_ids=["mission-control-crosscheck"],
        )
        auth = build_safe_state_exit_authorization(
            first,
            source_ref="release-board",
            actor_role_ids=["mission_commander"],
            evidence_ids=["release-check"],
        )
        self.assertEqual(verify_recovery_chain(state, receipt, second, auth)["status"], "FAIL")

    def test_missing_recovery_evidence_holds(self):
        state = post_clearance_safe_state()
        receipt = clearance_receipt(state)
        assessment = build_recovery_assessment(
            state,
            receipt,
            source_ref="instrument-sweep",
            evidence_ids=[],
            independent_check_ids=[],
        )
        self.assertEqual(assessment["status"], "FAULT_CLEARED_RECOVERY_INCOMPLETE")
        self.assertFalse(assessment["safe_state_exit_eligible"])
        self.assertIn("recovery_evidence_missing", assessment["release_blockers"])
        self.assertIn("independent_recovery_check_missing", assessment["release_blockers"])

    def test_apply_receipt_is_deterministic(self):
        state, receipt, assessment = self.assessment()
        auth = build_safe_state_exit_authorization(
            assessment,
            source_ref="release-board",
            actor_role_ids=["mission_commander"],
            evidence_ids=["release-check"],
        )
        first_state, first_receipt = apply_safe_state_exit(
            state,
            clearance_apply_receipt=receipt,
            assessment=assessment,
            authorization_receipt=auth,
        )
        second_state, second_receipt = apply_safe_state_exit(
            state,
            clearance_apply_receipt=receipt,
            assessment=assessment,
            authorization_receipt=auth,
        )
        self.assertEqual(first_state, second_state)
        self.assertEqual(first_receipt, second_receipt)
        self.assertEqual(len(first_receipt["apply_receipt_hash"]), 64)


if __name__ == "__main__":
    unittest.main()
