import unittest

from axm_star_sim.causal_cinematic_director import build_causal_cinematic_director
from axm_star_sim.living_interior_animation import build_living_interior_animation
from tests.test_exterior_operations_animation import ExteriorOperationsAnimationTests, storyboard


class CausalCinematicDirectorTests(unittest.TestCase):
    def build(self):
        scene, procedures, exterior = ExteriorOperationsAnimationTests().build()
        interior = build_living_interior_animation(scene, procedure_catalog=procedures)
        director = build_causal_cinematic_director(storyboard(), exterior, interior)
        return exterior, interior, director

    def test_cue_plan_preserves_source_segment_order_and_fractions(self):
        _, _, director = self.build()
        plan = director["cue_plans"][0]
        self.assertEqual(
            [row["source_segment_id"] for row in plan["shots"]],
            ["command_outbound", "observation_window", "telemetry_return"],
        )
        self.assertEqual(
            [row["display_fraction"] for row in plan["shots"]],
            [0.30, 0.24, 0.46],
        )
        self.assertTrue(all(not row["may_reorder_event"] for row in plan["shots"]))

    def test_recorded_probe_delta_focuses_telemetry_on_research_room(self):
        _, _, director = self.build()
        telemetry = director["cue_plans"][0]["shots"][2]
        self.assertEqual(telemetry["scene_mode"], "interior_follow")
        self.assertEqual(telemetry["focus_room_id"], "research_strategy")
        self.assertEqual(
            telemetry["camera_semantics"],
            "RECORDED_STATE_CHANGE_FOCUS_WITHOUT_VALUE_JUDGMENT",
        )

    def test_director_is_deterministic_and_cannot_rewrite_causality(self):
        first = self.build()[2]
        second = self.build()[2]
        self.assertEqual(first, second)
        self.assertEqual(first["director_hash"], second["director_hash"])
        self.assertEqual(first["authority"], "read_only_causal_camera_direction")
        self.assertFalse(first["renderer_may_reorder_events"])
        self.assertFalse(first["renderer_may_change_cue_timing_fractions"])
        self.assertFalse(first["renderer_may_retarget_event"])
        self.assertFalse(first["renderer_may_modify_world_state"])
        self.assertFalse(first["renderer_may_execute_operation"])

    def test_visual_detail_profiles_change_render_density_only(self):
        _, _, director = self.build()
        profiles = director["visual_detail_profiles"]
        self.assertEqual(set(profiles), {"eco", "standard", "rich"})
        self.assertLess(profiles["eco"]["particle_budget"], profiles["standard"]["particle_budget"])
        self.assertLess(profiles["standard"]["particle_budget"], profiles["rich"]["particle_budget"])
        self.assertTrue(director["renderer_may_adjust_visual_detail"])


if __name__ == "__main__":
    unittest.main()
