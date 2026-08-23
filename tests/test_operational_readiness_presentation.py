import json
import unittest
from pathlib import Path

from axm_star_sim.living_operations_bridge import enrich_storyboard
from axm_star_sim.living_operations_bridge_view import render_living_bridge
from axm_star_sim.temporal_renderer_adapter import (
    build_temporal_storyboard,
    load_verified_snapshot,
)
from tests.test_temporal_renderer_adapter import fixture_bytes


ROOT = Path(__file__).resolve().parents[1]


class OperationalReadinessPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        snapshot = load_verified_snapshot(**fixture_bytes())
        load = lambda name: json.loads(
            (ROOT / "data" / name).read_text(encoding="utf-8")
        )
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
        cls.source = render_living_bridge(
            cls.board,
            snapshot["import_receipt"],
        )

    def test_storyboard_includes_non_executable_readiness_contracts(self):
        readiness = self.board["operational_readiness"]
        self.assertEqual(
            readiness["schema"],
            "axm.operational-readiness-contract-catalog.v1",
        )
        self.assertGreater(readiness["contract_count"], 0)
        self.assertFalse(readiness["operationally_released"])
        self.assertFalse(readiness["may_modify_presentation_runtime"])
        self.assertFalse(readiness["may_execute_operation"])
        self.assertFalse(readiness["may_claim_nominal_with_residuals"])

    def test_living_profile_keeps_renderer_out_of_operational_authority(self):
        profile = self.board["living_operations"]
        self.assertEqual(profile["version"], "0.15.0-candidate")
        self.assertTrue(
            profile["authoritative_operational_release_engine_present"]
        )
        self.assertFalse(profile["renderer_may_apply_operational_release"])
        self.assertFalse(profile["renderer_may_classify_operating_mode"])
        self.assertFalse(profile["renderer_may_execute_operation"])
        self.assertFalse(profile["renderer_may_claim_nominal_with_residuals"])

    def test_renderer_shows_truthful_mode_and_capability_envelope(self):
        self.assertIn("NOMINAL IS NOT A DEFAULT", self.source)
        self.assertIn("DEGRADED OPERATIONS", self.source)
        self.assertIn("CAPABILITY ENVELOPE", self.source)
        self.assertIn("rendererMayApplyOperationalRelease:false", self.source)
        self.assertIn("rendererMayClassifyOperatingMode:false", self.source)
        self.assertIn("rendererMayExecuteOperation:false", self.source)
        self.assertIn("rendererMayClaimNominalWithResiduals:false", self.source)


if __name__ == "__main__":
    unittest.main()
