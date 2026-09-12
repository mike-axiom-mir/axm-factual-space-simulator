import json
import unittest
from pathlib import Path

from axm_star_sim.living_operations_bridge import enrich_storyboard
from axm_star_sim.living_operations_bridge_view import render_living_bridge
from axm_star_sim.temporal_renderer_adapter import build_temporal_storyboard, load_verified_snapshot
from tests.test_temporal_renderer_adapter import fixture_bytes


ROOT = Path(__file__).resolve().parents[1]


class LowGraphic3DPresentationTests(unittest.TestCase):
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

    def test_storyboard_contains_whole_ship_scene_projection(self):
        scene = self.board["low_graphic_3d_scene"]
        self.assertEqual(scene["version"], "0.12.0-candidate")
        self.assertEqual(scene["room_count"], 7)
        self.assertGreater(scene["station_count"], 0)
        self.assertGreater(len(scene["rehearsal_routes"]), 0)
        self.assertEqual(scene["authority"], "read_only_visual_projection")

    def test_living_profile_exposes_animation_without_world_authority(self):
        profile = self.board["living_operations"]
        self.assertEqual(profile["version"], "0.15.0-candidate")
        self.assertTrue(profile["low_graphic_3d_scene_present"])
        self.assertTrue(profile["renderer_may_animate"])
        self.assertFalse(profile["renderer_may_move_authoritative_crew"])
        self.assertFalse(profile["renderer_may_claim_fault_active_from_rehearsal"])
        self.assertFalse(profile["renderer_may_claim_physical_scene_geometry"])
        self.assertFalse(profile["may_execute_action"])

    def test_renderer_includes_whole_sim_scene_controls_and_assets(self):
        self.assertIn('id="scene25d"', self.source)
        self.assertIn("Ship cutaway · 2.5D", self.source)
        self.assertIn("Interior follow · 2.5D", self.source)
        self.assertIn("Exterior replay · low-poly", self.source)
        self.assertIn("Whole-sim 2.5D shell", self.source)
        self.assertIn("SHIP CUTAWAY · WHOLE INTERIOR GRAPH", self.source)
        self.assertIn("INTERIOR FOLLOW · ROOM ACTIVITY", self.source)
        self.assertIn("EXTERIOR REPLAY · PRESENTATION TRAJECTORY ONLY", self.source)

    def test_renderer_runtime_keeps_scene_authority_bounded(self):
        self.assertIn("lowGraphic3dVersion:'0.12.0-candidate'", self.source)
        self.assertIn("rendererMayAnimate:true", self.source)
        self.assertIn("rendererMayMoveAuthoritativeCrew:false", self.source)
        self.assertIn("rendererMayClaimFaultActiveFromRehearsal:false", self.source)
        self.assertIn("rendererMayRestoreResources:false", self.source)
        self.assertIn("WORLD WRITE / FAULT CLEAR / CREW MOVE / RESOURCE RESTORE: FORBIDDEN", self.source)

    def test_renderer_remains_offline_and_low_resolution(self):
        self.assertNotIn("<script src=", self.source)
        self.assertNotIn("three.js", self.source.lower())
        self.assertIn('canvas id="scene" width="480" height="270"', self.source)
        self.assertIn("external_dependencies\":[]", self.source)


if __name__ == "__main__":
    unittest.main()
