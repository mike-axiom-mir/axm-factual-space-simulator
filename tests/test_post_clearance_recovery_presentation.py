import json
import unittest
from pathlib import Path

from axm_star_sim.living_operations_bridge import enrich_storyboard
from axm_star_sim.living_operations_bridge_view import render_living_bridge
from axm_star_sim.temporal_renderer_adapter import build_temporal_storyboard, load_verified_snapshot
from tests.test_temporal_renderer_adapter import fixture_bytes


ROOT = Path(__file__).resolve().parents[1]


class PostClearanceRecoveryPresentationTests(unittest.TestCase):
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

    def test_storyboard_includes_non_mutating_recovery_contracts(self):
        recovery = self.board["post_clearance_recovery"]
        self.assertEqual(recovery["schema"], "axm.post-clearance-recovery-contract-catalog.v1")
        self.assertGreater(recovery["contract_count"], 0)
        self.assertFalse(recovery["safe_state_exited"])
        self.assertFalse(recovery["may_modify_presentation_runtime"])
        self.assertFalse(recovery["may_restore_resources"])

    def test_living_profile_keeps_renderer_out_of_recovery_authority(self):
        profile = self.board["living_operations"]
        self.assertEqual(profile["version"], "0.10.0-candidate")
        self.assertTrue(profile["authoritative_recovery_engine_present"])
        self.assertFalse(profile["renderer_may_apply_safe_state_exit"])
        self.assertFalse(profile["renderer_may_restore_resources"])
        self.assertFalse(profile["renderer_may_remove_load_sheds"])

    def test_renderer_exposes_recovery_truth_without_executing_it(self):
        self.assertIn("FAULT CLEARANCE ≠ FULL RECOVERY", self.source)
        self.assertIn("RECOVERY INCOMPLETE", self.source)
        self.assertIn("RECOVERY VERIFIED", self.source)
        self.assertIn("rendererMayApplySafeStateExit:false", self.source)
        self.assertIn("rendererMayRestoreResources:false", self.source)
        self.assertIn("safeStateExited:false", self.source)


if __name__ == "__main__":
    unittest.main()
