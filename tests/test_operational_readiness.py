import copy
import unittest

from axm_star_sim import ship_blueprint as ship
from axm_star_sim.operational_readiness import (
    READINESS_AUTHORITY_POLICY_ID,
    _hash,
    apply_operational_release,
    build_operational_readiness_contract,
    build_operational_readiness_contract_catalog,
    build_operational_readiness_envelope,
    derive_post_recovery_operating_mode,
    inspect_operation_readiness,
    verify_operational_release_chain,
)
from axm_star_sim.post_clearance_recovery import (
    build_recovery_assessment,
    build_safe_state_exit_authorization,
)
from tests.test_post_clearance_recovery import (
    clearance_receipt,
    post_clearance_safe_state,
)


class OperationalReadinessTests(unittest.TestCase):
    def release(self, state=None):
        state = state or post_clearance_safe_state()
        clearance = clearance_receipt(state)
        assessment = build_recovery_assessment(
            state,
            clearance,
            source_ref="post-clearance-operational-sweep",
            evidence_ids=["life-support-panel", "power-panel", "system-health-panel"],
            independent_check_ids=["mission-control-readiness-crosscheck"],
        )
        authorization = build_safe_state_exit_authorization(
            assessment,
            source_ref="operational-release-board",
            actor_role_ids=["mission_commander"],
            evidence_ids=["commander-release-check"],
        )
        released, receipt = apply_operational_release(
            state,
            clearance_apply_receipt=clearance,
            recovery_assessment=assessment,
            authorization_receipt=authorization,
        )
        envelope = build_operational_readiness_envelope(released, receipt)
        return state, clearance, assessment, authorization, released, receipt, envelope

    def operation(self, envelope, operation_id):
        return next(
            row for row in envelope["operations"]
            if row["operation_id"] == operation_id
        )

    def test_contract_forbids_nominal_claim_with_residuals(self):
        recovery = {
            "schema": "axm.post-clearance-recovery-contract.v1",
            "status": "RECOVERY_ENGINE_AVAILABLE_AFTER_APPLIED_VERIFIED_CLEARANCE",
            "source_failure_id": "co2_removal_degraded",
            "source_system_id": "eclss_atmosphere",
            "contract_id": "post-clearance-recovery:co2_removal_degraded:v1",
            "contract_hash": "recovery-contract",
        }
        contract = build_operational_readiness_contract(recovery)
        self.assertEqual(
            contract["status"],
            "OPERATIONAL_RELEASE_ENGINE_AVAILABLE_AFTER_VERIFIED_RECOVERY_CHAIN",
        )
        self.assertEqual(
            contract["mode_policy"]["truth_status"],
            "simulation_policy_candidate_not_canon",
        )
        self.assertFalse(contract["may_claim_nominal_with_residuals"])
        self.assertFalse(contract["may_execute_operation"])
        catalog = build_operational_readiness_contract_catalog({
            "schema": "axm.post-clearance-recovery-contract-catalog.v1",
            "contracts": [recovery],
        })
        self.assertEqual(catalog["contract_count"], 1)
        self.assertFalse(catalog["may_modify_presentation_runtime"])

    def test_residual_release_becomes_degraded_operations_not_nominal(self):
        _, _, assessment, _, released, receipt, _ = self.release()
        self.assertEqual(
            derive_post_recovery_operating_mode(assessment),
            "degraded_operations",
        )
        self.assertEqual(released["mode"], "degraded_operations")
        self.assertEqual(
            receipt["status"],
            "APPLIED_VERIFIED_DEGRADED_OPERATIONAL_RELEASE",
        )
        self.assertFalse(receipt["nominal_claim_allowed"])
        self.assertFalse(receipt["intermediate_nominal_state_persisted"])
        self.assertIn("load_sheds_remain", receipt["residual_indicators"])

    def test_intermediate_nominal_validation_state_is_not_persisted(self):
        original, _, _, _, released, receipt, _ = self.release()
        self.assertEqual(
            len(released["state_history"]),
            len(original["state_history"]) + 1,
        )
        self.assertIn(
            "apply_verified_operational_release",
            released["state_history"][-1]["reason"],
        )
        self.assertNotEqual(
            receipt["safe_state_exit_validation_state_hash"],
            released["state_hash"],
        )

    def test_release_preserves_every_non_bookkeeping_state_value(self):
        original, _, _, _, released, receipt, _ = self.release()
        for key in original:
            if key not in {"mode", "state_history", "state_hash"}:
                self.assertEqual(released[key], original[key], key)
        self.assertTrue(receipt["residual_state_preserved"])
        self.assertFalse(receipt["resource_values_restored"])
        self.assertFalse(receipt["load_sheds_removed_by_release"])
        self.assertTrue(ship.verify_ship_state(released)["valid"])

    def test_nominal_release_requires_no_residual_indicators(self):
        state = post_clearance_safe_state()
        state["power"]["shed_loads"] = []
        state["state_hash"] = ship.state_hash(state)
        _, _, assessment, _, released, receipt, envelope = self.release(state)
        self.assertEqual(assessment["status"], "NOMINAL_RECOVERY_RELEASE_ELIGIBLE")
        self.assertEqual(released["mode"], "nominal")
        self.assertTrue(receipt["nominal_claim_allowed"])
        self.assertEqual(receipt["residual_indicators"], [])
        self.assertEqual(envelope["operating_mode"], "nominal")

    def test_science_remains_held_while_its_load_is_shed(self):
        *_, envelope = self.release()
        science = self.operation(envelope, "science_payload_operations")
        self.assertEqual(science["status"], "HOLD")
        self.assertIn("science_payload_load_shed", science["blockers"])
        self.assertFalse(science["may_execute"])

    def test_irreversible_commitment_is_held_in_degraded_operations(self):
        *_, envelope = self.release()
        irreversible = self.operation(
            envelope,
            "irreversible_mission_commitment",
        )
        self.assertEqual(irreversible["status"], "HOLD")
        self.assertIn("operating_mode_not_nominal", irreversible["blockers"])
        self.assertIn("residual_state_remains", irreversible["blockers"])

    def test_degraded_communications_produces_limited_not_fake_nominal_access(self):
        state = post_clearance_safe_state()
        state["communications"]["availability"] = 0.6
        state["communications"]["telemetry_visibility_fraction"] = 0.7
        state["state_hash"] = ship.state_hash(state)
        *_, envelope = self.release(state)
        communications = self.operation(
            envelope,
            "high_bandwidth_communications",
        )
        self.assertEqual(communications["status"], "AVAILABLE_WITH_LIMITS")
        self.assertIn(
            "communications_availability_degraded",
            communications["limits"],
        )
        self.assertIn("telemetry_visibility_degraded", communications["limits"])

    def test_propulsion_loss_holds_navigation_and_docking(self):
        state = post_clearance_safe_state()
        state["navigation"]["propulsion_available"] = False
        state["state_hash"] = ship.state_hash(state)
        *_, envelope = self.release(state)
        navigation = self.operation(envelope, "precision_navigation_maneuver")
        docking = self.operation(envelope, "docking_and_transfer")
        self.assertEqual(navigation["status"], "HOLD")
        self.assertEqual(docking["status"], "HOLD")
        self.assertIn("propulsion_unavailable", navigation["blockers"])
        self.assertIn("propulsion_unavailable", docking["blockers"])

    def test_envelope_is_inspection_only(self):
        *_, envelope = self.release()
        self.assertEqual(envelope["authority"], "read_only_capability_envelope")
        self.assertFalse(envelope["may_execute_operation"])
        self.assertFalse(envelope["may_override_hold"])
        inspection = inspect_operation_readiness(
            envelope,
            "life_support_monitoring",
        )
        self.assertEqual(inspection["authority"], "inspection_only")
        self.assertFalse(inspection["may_execute"])
        with self.assertRaises(ValueError):
            inspect_operation_readiness(envelope, "invented_operation")

    def test_rehashed_receipt_cannot_claim_nominal_with_residuals(self):
        *_, released, receipt, _ = self.release()
        forged = copy.deepcopy(receipt)
        forged["mode_after"] = "nominal"
        forged["status"] = "APPLIED_VERIFIED_NOMINAL_OPERATIONAL_RELEASE"
        forged["nominal_claim_allowed"] = True
        raw = copy.deepcopy(forged)
        raw.pop("apply_receipt_hash")
        forged["apply_receipt_hash"] = _hash(
            raw,
            "AXM-OPERATIONAL-RELEASE-APPLY-RECEIPT-V1",
        )
        with self.assertRaises(ValueError):
            build_operational_readiness_envelope(released, forged)

    def test_state_drift_invalidates_release_chain(self):
        (
            original,
            clearance,
            assessment,
            authorization,
            released,
            receipt,
            _,
        ) = self.release()
        drifted = copy.deepcopy(released)
        drifted["communications"]["data_queue_gb"] += 0.5
        drifted["state_hash"] = ship.state_hash(drifted)
        result = verify_operational_release_chain(
            original,
            clearance_apply_receipt=clearance,
            recovery_assessment=assessment,
            authorization_receipt=authorization,
            released_state=drifted,
            operational_release_receipt=receipt,
        )
        self.assertEqual(result["status"], "FAIL")

    def test_release_and_envelope_are_deterministic(self):
        first = self.release()
        second = self.release()
        self.assertEqual(first[4], second[4])
        self.assertEqual(first[5], second[5])
        self.assertEqual(first[6], second[6])
        self.assertEqual(first[5]["authority_policy_id"], READINESS_AUTHORITY_POLICY_ID)
        self.assertEqual(len(first[5]["apply_receipt_hash"]), 64)


if __name__ == "__main__":
    unittest.main()
