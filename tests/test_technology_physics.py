from __future__ import annotations

import unittest

from axm_star_sim.generator import generate_system
from axm_star_sim.runtime import initial_runtime_state, preview_turn
from axm_star_sim.technology_core import eligible_core_ids, select_technology_core


def seed_for(core_id: str) -> str:
    for index in range(10000):
        seed = f"AXM-TECH-PHYS-{index:05d}"
        selected, _core, _receipt = select_technology_core(seed)
        if selected == core_id:
            return seed
    raise AssertionError(f"could not find seed for {core_id}")


class TechnologyPhysicsTests(unittest.TestCase):
    def preview_for(self, core_id: str):
        system = generate_system(seed_for(core_id)).to_dict()
        state = initial_runtime_state(system)
        action = next(
            (item for item in state["action_menu"]["actions"] if item["category"] == "instrument"),
            state["action_menu"]["actions"][0],
        )
        return system, preview_turn(system, state, action["action_id"])

    def test_every_eligible_core_builds_a_technology_physics_envelope(self):
        for core_id in eligible_core_ids():
            _system, preview = self.preview_for(core_id)
            envelope = preview["physics_expectation"]["technology_envelope"]
            self.assertEqual(envelope["selected_core_id"], core_id)
            self.assertIn("authority_rule", envelope)

    def test_published_generation_only_bounds_a_labelled_scenario(self):
        _system, preview = self.preview_for("orion_esm_crew_transport")
        physics = preview["physics_expectation"]
        power = physics["technology_envelope"]["power"]
        self.assertEqual(power["published_generation_kw"], 11)
        self.assertEqual(power["status"], "source_bounded_potential_scenario")
        self.assertLessEqual(
            physics["configuration"]["instrument_power_kw"],
            power["scenario_power_ceiling_kw"],
        )
        self.assertIn("not a claim", power["truth_note"])

    def test_hls_unknown_power_remains_unbounded_reference_scenario(self):
        _system, preview = self.preview_for("blue_moon_mk2_pathfinder_2027")
        power = preview["physics_expectation"]["technology_envelope"]["power"]
        self.assertIsNone(power["published_generation_kw"])
        self.assertEqual(power["status"], "unbounded_reference_scenario")
        self.assertIn("does not assert installed hardware", power["truth_note"])

    def test_transfer_delta_v_is_requirement_not_core_capability(self):
        _system, preview = self.preview_for("gateway_ppe_halo")
        physics = preview["physics_expectation"]
        self.assertGreaterEqual(physics["trajectory"]["total_delta_v_km_s"], 0)
        propulsion = physics["technology_envelope"]["propulsion"]
        self.assertEqual(propulsion["quantitative_performance_status"], "blocked_unknown")
        self.assertIn("environmental transfer requirement", propulsion["truth_note"])
        self.assertIn("delta_v_capability", propulsion["blocked_quantities"])


if __name__ == "__main__":
    unittest.main()
