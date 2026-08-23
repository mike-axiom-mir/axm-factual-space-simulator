import json
import unittest
from pathlib import Path

from axm_star_sim.living_operations_bridge import enrich_storyboard
from axm_star_sim.living_operations_bridge_view import render_living_bridge
from axm_star_sim.temporal_renderer_adapter import build_temporal_storyboard, load_verified_snapshot
from tests.test_temporal_renderer_adapter import fixture_bytes


ROOT = Path(__file__).resolve().parents[1]


class LivingInteriorAnimationPresentationTests(unittest.TestCase):
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

    def test_storyboard_contains_living_interior_contract(self):
        animation = self.board["living_interior_animation"]
        self.assertEqual(animation["version"], "0.13.0-candidate")
        self.assertEqual(len(animation["room_activity_profiles"]), 7)
        self.assertGreater(len(animation["portal_actors"]), 0)
        self.assertGreater(len(animation["crew_reenactment_tracks"]), 0)
        self.assertEqual(animation["authority"], "read_only_living_interior_presentation")

    def test_living_profile_exposes_animation_without_new_authority(self):
        profile = self.board["living_operations"]
        self.assertEqual(profile["version"], "0.13.0-candidate")
        self.assertTrue(profile["living_interior_animation_present"])
        self.assertTrue(profile["renderer_may_animate_room_ambience"])
        self.assertTrue(profile["renderer_may_animate_portals"])
        self.assertTrue(profile["renderer_may_animate_crew_reenactment"])
        self.assertTrue(profile["renderer_may_animate_abstract_machinery"])
        self.assertFalse(profile["renderer_may_open_authoritative_doors"])
        self.assertFalse(profile["renderer_may_move_authoritative_crew"])
        self.assertFalse(profile["renderer_may_claim_physical_hardware"])

    def test_renderer_contains_living_room_controls_and_truth_boundary(self):
        self.assertIn('id="interiorLife"', self.source)
        self.assertIn("Living interior v0.13", self.source)
        self.assertIn("ABSTRACT SYSTEM ACTIVITY · NOT HARDWARE REPLICA", self.source)
        self.assertIn("rendererMayOpenAuthoritativeDoors:false", self.source)
        self.assertIn("rendererMayMoveAuthoritativeCrew:false", self.source)
        self.assertIn("rendererMayClaimPhysicalHardware:false", self.source)
        self.assertIn("rendererMayExecuteRepair:false", self.source)

    def test_renderer_stays_offline_and_low_resolution(self):
        self.assertNotIn("<script src=", self.source)
        self.assertIn('canvas id="scene" width="480" height="270"', self.source)
        self.assertIn('"external_dependencies":[]', self.source)


if __name__ == "__main__":
    unittest.main()
