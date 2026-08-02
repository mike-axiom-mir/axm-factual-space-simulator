import copy
import unittest

from axm_star_sim.generator import generate_system
from axm_star_sim.technology_core import (
    build_ship_technology_profile,
    eligible_core_ids,
    load_technology_core_registry,
    load_exploration_function_map,
    select_technology_core,
    validate_technology_registry,
)
from axm_star_sim.validation import validate_system


class TechnologyCoreTests(unittest.TestCase):
    def test_registry_validates_no_invented_numeric_values(self):
        self.assertEqual(validate_technology_registry(), [])

    def test_equal_catalog_selection_is_deterministic(self):
        first = select_technology_core("AXM-TECH-SEED")
        second = select_technology_core("AXM-TECH-SEED")
        self.assertEqual(first, second)
        self.assertEqual(first[2]["weights"], "none; every eligible catalog core occupies one sorted slot")
        self.assertFalse(first[2]["manual_technology_choice"])

    def test_catalog_contains_four_2027_reference_lineages(self):
        self.assertEqual(
            eligible_core_ids(),
            [
                "blue_moon_mk2_pathfinder_2027",
                "gateway_ppe_halo",
                "orion_esm_crew_transport",
                "spacex_starship_hls_pathfinder_2027",
            ],
        )

    def test_draco_is_research_only_and_never_selectable(self):
        registry = load_technology_core_registry()
        research = registry["supporting_technologies"]["nuclear_thermal_research_envelope"]
        self.assertFalse(research["eligible_for_2027_reference_ship"])
        selected = {build_ship_technology_profile(f"DRACO-GATE-{i}")["selected_core_id"] for i in range(100)}
        self.assertNotIn("nuclear_thermal_research_envelope", selected)

    def test_seed_population_reaches_all_eligible_cores_without_weights(self):
        found = {build_ship_technology_profile(f"AXM-CORE-{i}")["selected_core_id"] for i in range(400)}
        self.assertEqual(found, set(eligible_core_ids()))

    def test_unknown_performance_remains_explicitly_blocked(self):
        for seed in ["AXM-U-1", "AXM-U-2", "AXM-U-3", "AXM-U-4"]:
            profile = build_ship_technology_profile(seed)
            self.assertTrue(profile["truth_contract"]["unknown_values_remain_unknown"])
            blocked = {row["quantity"] for row in profile["blocked_calculations"]}
            self.assertIn("crew_g_load", blocked)
            self.assertIn("mission_range", blocked)

    def test_gateway_nameplate_sum_is_derived_not_operational_claim(self):
        registry = load_technology_core_registry()
        value = registry["cores"]["gateway_ppe_halo"]["derived_parameters"]["installed_electric_thruster_nameplate_power"]
        self.assertEqual(value["value"], 60)
        self.assertEqual(value["formula_id"], "sum_nameplate_power")
        self.assertIn("not a simultaneous", value["notes"].lower())

    def test_orion_person_days_is_transparent_arithmetic(self):
        registry = load_technology_core_registry()
        value = registry["cores"]["orion_esm_crew_transport"]["derived_parameters"]["maximum_standalone_person_days"]
        self.assertEqual(value["value"], 84)
        self.assertEqual(value["formula_id"], "product_of_catalog_values")

    def test_reference_functions_never_claim_real_authority(self):
        mapping = load_exploration_function_map()
        self.assertTrue(mapping["policy"]["fiction_reference_is_inspiration_not_evidence"])
        self.assertEqual(mapping["functions"]["acceleration_load_management"]["status"], "no direct real technology")
        self.assertIn("faster-than-light propulsion", mapping["functions"]["centralized_energy_architecture"]["unavailable_claims"])

    def test_generated_system_embeds_source_pinned_technology_profile(self):
        data = generate_system("AXM-EMBED-TECH").to_dict()
        profile = data["ship"]["technology_core"]
        self.assertIn(profile["selected_core_id"], eligible_core_ids())
        self.assertEqual(profile["planning_horizon_year"], 2027)
        self.assertFalse(profile["selection_receipt"]["manual_technology_choice"])
        self.assertEqual(validate_system(copy.deepcopy(data)), [])

    def test_hls_pathfinders_do_not_invent_undisclosed_thrust_or_mass(self):
        registry = load_technology_core_registry()
        for core_id in ["spacex_starship_hls_pathfinder_2027", "blue_moon_mk2_pathfinder_2027"]:
            core = registry["cores"][core_id]
            keys = set(core["factual_parameters"])
            self.assertNotIn("wet_mass", keys)
            self.assertNotIn("thrust", keys)
            self.assertNotIn("specific_impulse", keys)
            self.assertTrue(any("mass" in x.lower() for x in core["unknown_parameters"]))


if __name__ == "__main__":
    unittest.main()
