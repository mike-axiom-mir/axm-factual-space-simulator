import unittest

from axm_star_sim.temporal_bridge_view import render_temporal_bridge
from axm_star_sim.temporal_renderer_adapter import build_temporal_storyboard, load_verified_snapshot
from tests.test_temporal_renderer_adapter import fixture_bytes


class TemporalBridgeViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        snapshot = load_verified_snapshot(**fixture_bytes())
        cls.source = render_temporal_bridge(build_temporal_storyboard(snapshot), snapshot["import_receipt"])

    def test_renderer_is_offline(self):
        self.assertNotIn("https://", self.source)
        self.assertNotIn("<script src=", self.source)

    def test_real_animation_loop_is_present(self):
        self.assertIn("requestAnimationFrame(loop)", self.source)
        self.assertIn("frameCount+=1", self.source)

    def test_runtime_authority_is_presentation_only(self):
        self.assertIn("authority:'presentation_state_only'", self.source)
        self.assertIn("mayAdvanceMissionTime:false", self.source)
        self.assertIn("mayAppendEvent:false", self.source)
        self.assertIn("mayChangeTruthLabels:false", self.source)
        self.assertIn("mayRetargetEvent:false", self.source)
        self.assertIn("mayModifyRuntimeResources:false", self.source)

    def test_source_and_display_clocks_are_visibly_separated(self):
        self.assertIn('id="missionClockLabel"', self.source)
        self.assertIn('id="displayClockLabel"', self.source)
        self.assertIn("SOURCE MISSION", self.source)
        self.assertIn("REPLAY DISPLAY", self.source)

    def test_inspect_only_presentation_controls_exist(self):
        self.assertIn('id="cameraSelect"', self.source)
        self.assertIn('id="labelSelect"', self.source)
        self.assertIn('id="inspectSelect"', self.source)
        self.assertIn("System overview", self.source)
        self.assertIn("Signal lane", self.source)

    def test_causal_replay_controls_and_delta_panel_exist(self):
        self.assertIn('id="replayScrubber"', self.source)
        self.assertIn('id="previousCue"', self.source)
        self.assertIn('id="nextCue"', self.source)
        self.assertIn('id="deltaPanel"', self.source)
        self.assertIn("recorded-simulation-event-delta", self.source)
        self.assertIn("scrubTo", self.source)

    def test_temporal_statuses_remain_honest(self):
        self.assertIn("UNKNOWN_NO_TIMESTAMP", self.source)
        self.assertIn("NONE_IN_IMPORTED_LEDGER_NOT_A_PREDICTION", self.source)

    def test_accessibility_holds_exist(self):
        self.assertIn("prefers-reduced-motion", self.source)
        self.assertIn("visibilitychange", self.source)


if __name__ == "__main__":
    unittest.main()
