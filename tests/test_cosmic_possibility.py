import copy
import unittest

from axm_star_sim.cosmic_possibility import (
    load_cosmic_possibility_registry,
    reasoned_candidate_matrix,
    system_environment,
    validate_cosmic_possibility_registry,
)
from axm_star_sim.generator import generate_system


class CosmicPossibilityTests(unittest.TestCase):
    def setUp(self):
        self.system = generate_system("AXM-COSMIC-POSSIBILITY-TEST").to_dict()

    def test_registry_validates(self):
        self.assertEqual(validate_cosmic_possibility_registry(), [])

    def test_registry_rejects_life_like_equals_life_drift(self):
        registry = copy.deepcopy(load_cosmic_possibility_registry())
        registry["policy"]["life_like_behavior_is_not_automatically_life"] = False
        errors = validate_cosmic_possibility_registry(registry)
        self.assertTrue(any("life_like_behavior" in error for error in errors))

    def test_environment_does_not_claim_solvent_or_life(self):
        environment = system_environment(self.system)
        self.assertIn("equilibrium_temperature_k", environment)
        self.assertNotIn("life_present", environment)
        self.assertIn("not surface temperature", environment["truth_note"])

    def test_reasoned_matrix_is_reproducible_and_source_bounded(self):
        first = reasoned_candidate_matrix(self.system, "FORGE-SEED-A")
        second = reasoned_candidate_matrix(self.system, "FORGE-SEED-A")
        self.assertEqual(first, second)
        self.assertEqual(first["candidate_count"], 72)
        self.assertEqual(len(first["shortlist"]), 12)
        self.assertTrue(all(item["source_ids"] for item in first["shortlist"]))

    def test_forge_seed_can_change_selected_lens_without_changing_world(self):
        first = reasoned_candidate_matrix(self.system, "FORGE-SEED-A")
        selections = {
            reasoned_candidate_matrix(self.system, f"FORGE-SEED-{i}")["selected_candidate_id"]
            for i in range(20)
        }
        self.assertGreater(len(selections), 1)
        self.assertEqual(first["environment"], system_environment(self.system))


if __name__ == "__main__":
    unittest.main()
