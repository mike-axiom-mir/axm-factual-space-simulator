import copy
import hashlib
import json
import unittest
from pathlib import Path

from axm_star_sim.temporal_renderer_adapter import (
    build_renderer_authorization,
    build_temporal_storyboard,
    build_event_state_change_receipt,
    derive_mission_time_receipts,
    load_verified_snapshot,
    sample_storyboard,
    verify_main_simulator_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "output" / "persistent_atlas_demo" / "expedition_alpha"
REPOSITORY = "mike-axiom-mir/axm-factual-space-simulator"
COMMIT = "f7939f24faf970e32d65b561ec5b2f8eb1e41d70"


def fixture_bytes():
    return {
        "system_bytes": (FIXTURE / "system.json").read_bytes(),
        "runtime_bytes": (FIXTURE / "runtime_state.json").read_bytes(),
        "event_ledger_bytes": (FIXTURE / "event_ledger.jsonl").read_bytes(),
        "manifest_bytes": (FIXTURE / "manifest.json").read_bytes(),
        "source_repository": REPOSITORY,
        "source_commit": COMMIT,
    }


class TemporalRendererAdapterTests(unittest.TestCase):
    def snapshot(self):
        return load_verified_snapshot(**fixture_bytes())

    def test_current_output_fixture_imports(self):
        receipt = verify_main_simulator_snapshot(**fixture_bytes())
        self.assertEqual(receipt["status"], "IMPORT_VALID")
        self.assertEqual(receipt["event_count"], 4)

    def test_adapter_never_gains_world_authority(self):
        receipt = verify_main_simulator_snapshot(**fixture_bytes())
        self.assertEqual(receipt["authority"], "read_only_renderer_input")
        self.assertFalse(receipt["may_modify_world_state"])
        self.assertFalse(receipt["may_append_events"])

    def test_tamper_is_held(self):
        values = fixture_bytes()
        values["runtime_bytes"] += b" "
        receipt = verify_main_simulator_snapshot(**values)
        self.assertEqual(receipt["status"], "HOLD_IMPORT_INVALID")
        self.assertTrue(any("runtime_state.json" in row for row in receipt["failures"]))

    def test_broken_chain_is_held_after_hash_update(self):
        values = fixture_bytes()
        lines = values["event_ledger_bytes"].decode().splitlines()
        event = json.loads(lines[1])
        event["previous_event_hash"] = "0" * 64
        lines[1] = json.dumps(event)
        ledger = ("\n".join(lines) + "\n").encode()
        manifest = json.loads(values["manifest_bytes"])
        manifest["files"]["event_ledger.jsonl"] = hashlib.sha256(ledger).hexdigest()
        values["event_ledger_bytes"] = ledger
        values["manifest_bytes"] = json.dumps(manifest).encode()
        receipt = verify_main_simulator_snapshot(**values)
        self.assertEqual(receipt["status"], "HOLD_IMPORT_INVALID")
        self.assertTrue(any("previous-event link mismatch" in row for row in receipt["failures"]))

    def test_storyboard_is_deterministic_and_non_mutating(self):
        snapshot = self.snapshot()
        before = copy.deepcopy(snapshot)
        first = build_temporal_storyboard(snapshot)
        second = build_temporal_storyboard(snapshot)
        self.assertEqual(first, second)
        self.assertEqual(snapshot, before)

    def test_orbits_are_presentation_geometry_not_ephemerides(self):
        board = build_temporal_storyboard(self.snapshot())
        self.assertTrue(all(row["position_authority"] == "presentation_only_simulation_geometry" for row in board["planets"]))
        self.assertTrue(all(not row["precision_ephemeris_claimed"] for row in board["planets"]))

    def test_sample_cannot_advance_mission_or_append_event(self):
        sample = sample_storyboard(build_temporal_storyboard(self.snapshot()), 6.0)
        self.assertFalse(sample["may_advance_mission_time"])
        self.assertFalse(sample["may_append_event"])
        self.assertEqual(sample["authority"], "presentation_state_only")

    def test_mission_receipts_reconcile_without_becoming_a_clock(self):
        snapshot = self.snapshot()
        reconstruction = derive_mission_time_receipts(
            snapshot["events"],
            snapshot["runtime"]["mission_time_hours"],
        )
        self.assertEqual(reconstruction["status"], "CONSISTENT_RECONSTRUCTION")
        self.assertEqual(reconstruction["source_current_mission_time_hours"], 3.0)
        self.assertEqual(
            [
                (row["mission_time_start_hours"], row["mission_time_end_hours"])
                for row in reconstruction["receipts"]
            ],
            [(0.0, 1.0), (1.0, 1.5), (1.5, 2.5), (2.5, 3.0)],
        )
        self.assertTrue(all(not row["may_advance_mission_time"] for row in reconstruction["receipts"]))
        self.assertEqual(
            reconstruction["future_receipt_status"],
            "NONE_IN_IMPORTED_LEDGER_NOT_A_PREDICTION",
        )

    def test_missing_duration_holds_instead_of_fabricating_event_times(self):
        snapshot = self.snapshot()
        events = copy.deepcopy(snapshot["events"])
        del events[1]["outcome"]["resource_deltas"]["mission_time_hours"]
        reconstruction = derive_mission_time_receipts(events, 3.0)
        self.assertEqual(reconstruction["status"], "HOLD_TEMPORAL_RECONSTRUCTION")
        self.assertTrue(reconstruction["failures"])
        self.assertTrue(
            all(row["mission_time_start_hours"] is None for row in reconstruction["receipts"])
        )

    def test_storyboard_separates_source_clock_and_renderer_clock(self):
        board = build_temporal_storyboard(self.snapshot())
        self.assertEqual(board["mission_time_hours"], 3.0)
        self.assertEqual(board["mission_clock_authority"], "copied_read_only_runtime_source_state")
        self.assertEqual(
            board["temporal_reconstruction"]["clock_separation"],
            "source_mission_clock_is_distinct_from_renderer_display_clock",
        )
        self.assertEqual(board["cues"][-1]["temporal_receipt"]["temporal_relation"], "ledger_head")

    def test_camera_and_label_profiles_are_presentation_only(self):
        profiles = build_temporal_storyboard(self.snapshot())["presentation_profiles"]
        self.assertEqual(
            [row["id"] for row in profiles["camera_presets"]],
            ["overview", "target_focus", "signal_lane"],
        )
        self.assertTrue(all(not row["changes_semantics"] for row in profiles["camera_presets"]))
        self.assertFalse(profiles["may_change_world_state"])
        self.assertFalse(profiles["may_change_history"])
        self.assertFalse(profiles["may_change_truth_labels"])
        self.assertFalse(profiles["replay_scrubber"]["may_advance_mission_time"])
        self.assertFalse(profiles["object_inspector"]["may_retarget_event"])

    def test_state_change_receipts_preserve_direction_without_value_judgment(self):
        board = build_temporal_storyboard(self.snapshot())
        receipt = board["cues"][0]["state_change_receipt"]
        self.assertEqual(receipt["status"], "STATE_CHANGES_VALID")
        self.assertEqual(
            [row["resource_id"] for row in receipt["changes"]],
            ["mission_time_hours", "reactor_reserve_percent", "heat_percent", "knowledge_points"],
        )
        self.assertEqual(receipt["changes"][0]["delta"], 1.0)
        self.assertEqual(receipt["changes"][1]["direction"], "decrease")
        self.assertTrue(all(row["value_judgment"] == "not_assigned" for row in receipt["changes"]))
        self.assertTrue(all(not row["may_modify_runtime_resource"] for row in receipt["changes"]))

    def test_non_finite_state_change_is_held(self):
        event = copy.deepcopy(self.snapshot()["events"][0])
        event["outcome"]["resource_deltas"]["heat_percent"] = "not-a-number"
        receipt = build_event_state_change_receipt(event)
        self.assertEqual(receipt["status"], "HOLD_STATE_CHANGES_INVALID")
        row = next(item for item in receipt["changes"] if item["resource_id"] == "heat_percent")
        self.assertIsNone(row["delta"])
        self.assertTrue(receipt["failures"])

    def test_existing_renderer_gate_authorizes_animation_not_history_rewrite(self):
        authorization = build_renderer_authorization(self.snapshot()["import_receipt"])
        packet = authorization["reconstruction_packet"]
        self.assertEqual(authorization["authority"], "renderer_authorized_presentation_only")
        self.assertIn("animation", packet["renderer_may_change"])
        self.assertIn("historical_state", packet["renderer_may_not_change"])
        self.assertFalse(authorization["may_modify_world_state"])
        self.assertFalse(authorization["may_modify_history"])


if __name__ == "__main__":
    unittest.main()
