import copy
import unittest

from axm_star_sim.generator import generate_system
from axm_star_sim.runtime import initial_runtime_state
from axm_star_sim.command import crew_assessment
from axm_star_sim.rooted_crew import (
    ELIGIBLE,
    HOLD,
    INELIGIBLE,
    RootIntegrityError,
    evaluate_action_candidate,
    evolve_derived_principles,
    generate_principled_options,
    load_default_crew,
    load_root_kernel,
    root_commitment,
    verify_default_crew_binding,
    verify_derived_principles,
    verify_root_kernel,
)


class ImmutableRootCrewTests(unittest.TestCase):
    def test_exact_four_roots_and_order(self):
        kernel = load_root_kernel()
        self.assertEqual(
            [row["id"] for row in kernel["roots"]],
            [
                "truth_source_truth",
                "continuity_no_loss",
                "agency_no_takeover",
                "wisdom_over_speed",
            ],
        )

    def test_root_commitment_is_valid(self):
        kernel = load_root_kernel()
        self.assertEqual(kernel["root_commitment_sha256"], root_commitment(kernel))
        self.assertTrue(verify_root_kernel(kernel)["valid"])

    def test_default_crew_is_bound_to_roots(self):
        kernel = load_root_kernel()
        crew = load_default_crew()
        self.assertTrue(verify_default_crew_binding(crew, kernel)["valid"])
        self.assertEqual(crew["root_kernel_binding"]["binding"], "IMMUTABLE_MAINLINE")

    def test_no_crew_seat_can_override_roots(self):
        crew = load_default_crew()
        for row in crew["crew_roles"] + crew["command_presence"]:
            self.assertFalse(row["root_override_authority"])

    def test_root_mutation_is_detected(self):
        kernel = load_root_kernel()
        tampered = copy.deepcopy(kernel)
        tampered["roots"][0]["name"] = "Convenient Story"
        with self.assertRaises(RootIntegrityError):
            verify_root_kernel(tampered)

    def test_efficiency_does_not_rescue_theft(self):
        candidate = {
            "candidate_id": "rob-farm-tools",
            "label": "Rob the farmer for tools",
            "evidence_status": "known",
            "takes_property_without_consent": True,
            "coercive": True,
            "immediate_utility": 1.0,
            "long_term_utility": 0.1,
            "systemic_damage": 0.9,
            "destructive_shortcut": True,
            "legitimate_alternatives": ["borrow", "repair", "work", "trade"],
            "efficiency": 1.0,
        }
        result = evaluate_action_candidate(candidate)
        self.assertEqual(result["overall_verdict"], INELIGIBLE)
        self.assertIsNone(result["efficiency_score"])

    def test_missing_consent_holds_instead_of_takeover(self):
        result = evaluate_action_candidate({
            "candidate_id": "use-private-lab",
            "label": "Use another crew member's private lab",
            "consent_required": True,
            "consent_status": "unknown",
            "role_authorized": False,
            "immediate_utility": 0.8,
            "long_term_utility": 0.7,
        })
        self.assertEqual(result["overall_verdict"], HOLD)

    def test_reversible_truthful_cooperation_is_eligible(self):
        result = evaluate_action_candidate({
            "candidate_id": "borrow-tools",
            "label": "Ask to borrow tools and offer repair work",
            "evidence_status": "known",
            "recovery_path": True,
            "consent_required": True,
            "consent_status": "granted",
            "role_authorized": True,
            "immediate_utility": 0.65,
            "long_term_utility": 0.85,
            "learning_value": 0.3,
            "repair_value": 0.8,
            "proportionality": 1.0,
            "systemic_damage": 0.0,
            "efficiency": 0.6,
        })
        self.assertEqual(result["overall_verdict"], ELIGIBLE)

    def test_principled_generation_rejects_fast_robbery(self):
        options = [
            {
                "candidate_id": "rob",
                "label": "Rob tools",
                "takes_property_without_consent": True,
                "coercive": True,
                "destructive_shortcut": True,
                "legitimate_alternatives": ["borrow"],
                "immediate_utility": 1.0,
                "long_term_utility": 0.0,
                "efficiency": 1.0,
            },
            {
                "candidate_id": "borrow",
                "label": "Borrow tools with consent",
                "consent_required": True,
                "consent_status": "granted",
                "immediate_utility": 0.6,
                "long_term_utility": 0.9,
                "repair_value": 0.5,
                "proportionality": 1.0,
                "efficiency": 0.55,
            },
        ]
        result = generate_principled_options("obtain tools", options)
        self.assertEqual(result["recommended_option_id"], "borrow")
        self.assertEqual(result["rejected_options"][0]["option"]["candidate_id"], "rob")

    def test_unsupported_certainty_is_held(self):
        result = evaluate_action_candidate({
            "candidate_id": "declare-life",
            "label": "Declare confirmed life from one ambiguous signal",
            "evidence_status": "unverified",
            "acts_as_if_certain": True,
            "promotes_unverified_claim": False,
            "immediate_utility": 0.9,
            "long_term_utility": 0.2,
        })
        self.assertEqual(result["overall_verdict"], HOLD)

    def test_history_destruction_is_ineligible(self):
        result = evaluate_action_candidate({
            "candidate_id": "erase-ledger",
            "label": "Erase inconvenient expedition history",
            "destroys_history": True,
            "immediate_utility": 0.9,
        })
        self.assertEqual(result["overall_verdict"], INELIGIBLE)

    def test_derived_principles_may_grow(self):
        kernel = load_root_kernel()
        state = evolve_derived_principles({}, [
            {
                "principle_id": "ask_before_shared_resource_use",
                "statement": "Ask before reallocating a shared crew resource unless an immediate reversible safety action is required.",
                "derived_from_roots": ["agency_no_takeover", "wisdom_over_speed"],
                "evidence_or_lesson_receipts": ["lesson-001"],
            }
        ], kernel["root_commitment_sha256"])
        self.assertTrue(verify_derived_principles(state)["valid"])
        self.assertEqual(len(state["derived_principles"]), 1)

    def test_derived_principles_cannot_modify_roots(self):
        kernel = load_root_kernel()
        with self.assertRaises(RootIntegrityError):
            evolve_derived_principles({}, [
                {
                    "principle_id": "speed-first",
                    "statement": "Speed overrides wisdom.",
                    "replace_roots": True,
                }
            ], kernel["root_commitment_sha256"])

    def test_derived_chain_tamper_is_detected(self):
        kernel = load_root_kernel()
        state = evolve_derived_principles({}, [
            {
                "principle_id": "preserve-probe-evidence",
                "statement": "Preserve original probe telemetry before transforming it.",
                "derived_from_roots": ["truth_source_truth", "continuity_no_loss"],
            }
        ], kernel["root_commitment_sha256"])
        state["derived_principles"][0]["statement"] = "Rewrite it."
        self.assertFalse(verify_derived_principles(state)["valid"])

    def test_existing_crew_assessment_contains_roots(self):
        system = generate_system("AXM-V012-CREW-ASSESSMENT").to_dict()
        state = initial_runtime_state(system)
        assessment = crew_assessment(system, state)
        self.assertEqual(
            assessment["immutable_root_kernel"]["root_commitment_sha256"],
            load_root_kernel()["root_commitment_sha256"],
        )
        self.assertTrue(all("root_evaluation" in row for row in assessment["actions"]))
        recommended = next(row for row in assessment["actions"] if row["action"] == assessment["recommended_action"])
        self.assertTrue(recommended["root_eligible"])

    def test_existing_crew_assessment_remains_deterministic(self):
        system = generate_system("AXM-V012-DETERMINISM").to_dict()
        state = initial_runtime_state(system)
        self.assertEqual(crew_assessment(system, state), crew_assessment(system, state))


if __name__ == "__main__":
    unittest.main()
