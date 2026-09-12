import json
import unittest
from pathlib import Path

from axm_star_sim.living_operations_bridge import enrich_storyboard
from axm_star_sim.living_operations_bridge_view import render_living_bridge
from axm_star_sim.temporal_renderer_adapter import build_temporal_storyboard, load_verified_snapshot
from tests.test_temporal_renderer_adapter import fixture_bytes

ROOT = Path(__file__).resolve().parents[1]


class InteractiveExplorationPresentationTests(unittest.TestCase):
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

    def test_storyboard_contains_interactive_exploration_contract(self):
        exploration = self.board["interactive_exploration"]
        self.assertEqual(exploration["version"], "0.15.0-candidate")
        self.assertGreater(exploration["target_count"], 0)
        ids = {row["target_id"] for row in exploration["targets"]}
        self.assertIn("room:command_deck", ids)
        self.assertIn("station:medical_station", ids)
        self.assertEqual(exploration["authority"], "read_only_interactive_exploration_presentation")

    def test_living_profile_exposes_exploration_without_world_authority(self):
        profile = self.board["living_operations"]
        self.assertEqual(profile["version"], "0.15.0-candidate")
        self.assertTrue(profile["interactive_exploration_present"])
        self.assertTrue(profile["renderer_may_select_presentation_target"])
        self.assertTrue(profile["renderer_may_inspect_declared_source_metadata"])
        self.assertTrue(profile["renderer_may_follow_existing_presentation_context"])
        self.assertFalse(profile["renderer_may_change_authoritative_selection"])
        self.assertFalse(profile["renderer_may_move_authoritative_crew"])
        self.assertFalse(profile["renderer_may_move_authoritative_robotics"])
        self.assertFalse(profile["renderer_may_execute_operation"])
        self.assertFalse(profile["may_retarget_event"])

    def test_renderer_has_touch_friendly_explorer_and_inspector(self):
        self.assertIn('id="explorationFollow"', self.source)
        self.assertIn('id="explorationTarget"', self.source)
        self.assertIn('id="explorePrev"', self.source)
        self.assertIn('id="exploreNext"', self.source)
        self.assertIn("Interactive explorer v0.15", self.source)
        self.assertIn("INSPECT / FOLLOW ONLY · NO WORLD COMMAND", self.source)
        self.assertIn("canvas.addEventListener('pointerdown'", self.source)
        self.assertIn("tap a room in cutaway to inspect/follow it", self.source)

    def test_renderer_runtime_keeps_exploration_bounded(self):
        self.assertIn("interactiveExplorationVersion:'0.15.0-candidate'", self.source)
        self.assertIn("rendererMaySelectPresentationTarget:true", self.source)
        self.assertIn("rendererMayInspectDeclaredSourceMetadata:true", self.source)
        self.assertIn("rendererMayChangeAuthoritativeSelection:false", self.source)
        self.assertIn("rendererMayRetargetEvent:false", self.source)
        self.assertIn("rendererMayMoveAuthoritativeCrew:false", self.source)
        self.assertIn("rendererMayMoveAuthoritativeRobotics:false", self.source)
        self.assertIn("rendererMayExecuteOperation:false", self.source)
        self.assertIn("rendererMayModifyWorldState:false", self.source)

    def test_renderer_remains_offline_and_low_resolution(self):
        self.assertNotIn("<script src=", self.source)
        self.assertNotIn("three.js", self.source.lower())
        self.assertIn('canvas id="scene" width="480" height="270"', self.source)


if __name__ == "__main__":
    unittest.main()
