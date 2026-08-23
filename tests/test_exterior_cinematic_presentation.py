import json
import unittest
from pathlib import Path

from axm_star_sim.living_operations_bridge import enrich_storyboard
from axm_star_sim.living_operations_bridge_view import render_living_bridge
from axm_star_sim.temporal_renderer_adapter import build_temporal_storyboard, load_verified_snapshot
from tests.test_temporal_renderer_adapter import fixture_bytes

ROOT = Path(__file__).resolve().parents[1]


class ExteriorCinematicPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        snapshot = load_verified_snapshot(**fixture_bytes())
        load = lambda name: json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))
        cls.board = enrich_storyboard(
            build_temporal_storyboard(snapshot),
            snapshot["runtime"],
            failure_registry=load("ship_failure_mode_registry.json"),
            station_registry=load("crew_station_display_registry.json"),
            blueprint_registry=load("ship_system_blueprint_registry.json"),
            interface_graph=load("ship_interface_graph.json"),
            interior_registry=load("ship_interior_archetype_registry.json"),
            room_interaction_registry=load("room_interaction_registry.json"),
        )
        cls.source = render_living_bridge(cls.board, snapshot["import_receipt"])

    def test_storyboard_contains_exterior_and_cinematic_contracts(self):
        exterior = self.board["exterior_operations_animation"]
        director = self.board["causal_cinematic_director"]
        self.assertEqual(exterior["version"], "0.14.0-candidate")
        self.assertGreater(len(exterior["module_actors"]), 0)
        self.assertGreater(len(exterior["system_actors"]), 0)
        self.assertEqual(director["version"], "0.14.0-candidate")
        self.assertEqual(director["cue_plan_count"], len(self.board["cues"]))

    def test_living_profile_exposes_new_animation_without_execution_authority(self):
        profile = self.board["living_operations"]
        self.assertEqual(profile["version"], "0.14.0-candidate")
        self.assertTrue(profile["exterior_operations_animation_present"])
        self.assertTrue(profile["causal_cinematic_director_present"])
        self.assertTrue(profile["renderer_may_animate_exterior_capability_actors"])
        self.assertTrue(profile["renderer_may_route_camera_from_immutable_cues"])
        self.assertTrue(profile["renderer_may_adjust_visual_detail"])
        self.assertFalse(profile["renderer_may_execute_exterior_operation"])
        self.assertFalse(profile["renderer_may_apply_thrust"])
        self.assertFalse(profile["renderer_may_dock"])
        self.assertFalse(profile["renderer_may_begin_eva"])
        self.assertFalse(profile["renderer_may_deploy_probe"])
        self.assertFalse(profile["renderer_may_reorder_events"])

    def test_renderer_contains_exterior_cinematic_and_quality_controls(self):
        self.assertIn('id="exteriorOps"', self.source)
        self.assertIn('id="cinematicDirector"', self.source)
        self.assertIn('id="visualDetail"', self.source)
        self.assertIn("Exterior operations v0.14", self.source)
        self.assertIn("Causal cinematic director v0.14", self.source)
        self.assertIn("NO THRUST / DOCK / EVA / PROBE EXECUTION", self.source)
        self.assertIn("rendererMayApplyThrust:false", self.source)
        self.assertIn("rendererMayDock:false", self.source)
        self.assertIn("rendererMayBeginEva:false", self.source)
        self.assertIn("rendererMayDeployProbe:false", self.source)
        self.assertIn("rendererMayReorderEvents:false", self.source)
        self.assertIn("rendererMayChangeCueTimingFractions:false", self.source)

    def test_renderer_remains_offline_and_low_resolution(self):
        self.assertNotIn("<script src=", self.source)
        self.assertNotIn("three.js", self.source.lower())
        self.assertIn('canvas id="scene" width="480" height="270"', self.source)


if __name__ == "__main__":
    unittest.main()
