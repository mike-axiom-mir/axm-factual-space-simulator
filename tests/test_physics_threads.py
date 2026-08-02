from __future__ import annotations

import copy
import unittest

from axm_star_sim.generator import generate_system
from axm_star_sim.runtime import (
    initial_runtime_state,
    preview_turn,
    resolve_turn,
    verify_recorded_event,
)
from axm_star_sim.thread_engine import build_action_menu


class PhysicsAndThreadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.system = generate_system("AXM-V04-PHYSICS-THREADS").to_dict()
        self.state = initial_runtime_state(self.system)

    def _first_action(self, category: str | None = None) -> dict:
        rows = self.state["action_menu"]["actions"]
        if category:
            for row in rows:
                if row["category"] == category:
                    return row
        return rows[0]

    def test_preview_contains_complete_pre_entropy_physics(self) -> None:
        preview = preview_turn(self.system, self.state, "1")
        physics = preview["physics_expectation"]
        self.assertEqual(preview["schema"], "axm.turn-preview.v1")
        self.assertIn("orbital_state", physics)
        self.assertIn("sensor", physics)
        self.assertIn("thermal", physics)
        self.assertIn("radiation", physics)
        self.assertIn("communications", physics)
        self.assertIn("trajectory", physics)
        self.assertGreater(physics["sensor"]["expected_snr"], 0)
        self.assertGreaterEqual(physics["communications"]["one_way_light_time_s"], 0)
        self.assertGreater(physics["trajectory"]["transfer_time_days"], 0)
        self.assertAlmostEqual(
            sum(row["probability"] for row in preview["probability_snapshot"]),
            1.0,
            places=6,
        )
        self.assertIn("no selected future outcome", preview["honesty"].lower())

    def test_orbital_phase_and_flux_change_with_mission_time(self) -> None:
        first = preview_turn(self.system, self.state, "1")["physics_expectation"]
        later_state = copy.deepcopy(self.state)
        later_state["mission_time_hours"] += 240.0
        later_state["action_menu"] = build_action_menu(self.system, later_state)
        action_id = later_state["action_menu"]["actions"][0]["action_id"]
        later = preview_turn(self.system, later_state, action_id)["physics_expectation"]
        self.assertNotEqual(first["orbital_state"]["true_anomaly_deg"], later["orbital_state"]["true_anomaly_deg"])
        self.assertNotEqual(first["stellar_flux"]["value_w_m2"], later["stellar_flux"]["value_w_m2"])

    def test_event_records_expected_and_realized_measurement_separately(self) -> None:
        event, updated = resolve_turn(
            system=self.system,
            state=self.state,
            action="1",
            entropy_mode="deterministic",
        )
        self.assertIn("physics_expectation", event)
        measurement = event["outcome"]["observation"]["measurement"]
        self.assertEqual(measurement["expected_snr"], event["physics_expectation"]["sensor"]["expected_snr"])
        self.assertIn("realized_snr", measurement)
        self.assertIn("sensor_noise", event["rolls"])
        self.assertGreater(updated["mission_time_hours"], self.state["mission_time_hours"])

    def test_dynamic_menu_is_regenerated_from_opened_threads(self) -> None:
        initial_ids = {row["action_id"] for row in self.state["action_menu"]["actions"]}
        event, updated = resolve_turn(
            system=self.system,
            state=self.state,
            action="1",
            entropy_mode="deterministic",
        )
        next_rows = updated["action_menu"]["actions"]
        self.assertEqual(updated["action_menu"]["generated_from_turn"], 1)
        self.assertTrue(updated["action_menu"]["active_thread_ids"])
        self.assertTrue(any(row["source_thread"] != event["opportunity_id"] for row in next_rows))
        self.assertTrue(any(row["action_id"] not in initial_ids for row in next_rows))
        self.assertEqual(event["new_action_menu"], updated["action_menu"])

    def test_probe_launch_creates_in_flight_state_and_followup_thread(self) -> None:
        probe_system = generate_system("AXM-PROBE-0").to_dict()
        probe_state = initial_runtime_state(probe_system)
        probe = next(row for row in probe_state["action_menu"]["actions"] if row["category"] == "probe")
        before_count = probe_state["resources"]["probe_count"]
        _event, updated = resolve_turn(
            system=probe_system,
            state=probe_state,
            action=probe["action_id"],
            entropy_mode="deterministic",
        )
        self.assertEqual(updated["resources"]["probe_count"], before_count - 1)
        self.assertTrue(updated["active_probes"])
        self.assertEqual(updated["active_probes"][0]["status"], "in-flight")
        self.assertIn("probe-in-flight", updated["threads"])
        labels = [row["label"].lower() for row in updated["action_menu"]["actions"]]
        self.assertTrue(any("probe" in label or "telemetry" in label for label in labels))

    def test_impossible_probe_launches_are_removed_when_inventory_is_empty(self) -> None:
        state = copy.deepcopy(self.state)
        state["resources"]["probe_count"] = 0
        menu = build_action_menu(self.system, state)
        for row in menu["actions"]:
            if row["category"] == "probe":
                self.assertTrue(
                    row["parameters"].get("wait_for_probe")
                    or row["parameters"].get("remote_only")
                    or row["parameters"].get("trajectory_correction")
                    or row["parameters"].get("relay_mode")
                )

    def test_resolved_threads_fall_back_to_explicit_mission_continuation(self) -> None:
        state = copy.deepcopy(self.state)
        state["turn"] = 12
        for thread in state["threads"].values():
            thread["status"] = "resolved-provisional"
        state["resources"]["heat_percent"] = 20
        state["resources"]["sensor_health_percent"] = 90
        state["resources"]["reactor_reserve_percent"] = 80
        menu = build_action_menu(self.system, state)
        self.assertEqual(len(menu["actions"]), 3)
        self.assertTrue(all(row["source_thread"].startswith("mission-continuation:") for row in menu["actions"]))

    def test_physics_tampering_breaks_replay_verification(self) -> None:
        event, _updated = resolve_turn(
            system=self.system,
            state=self.state,
            action="1",
            entropy_mode="deterministic",
        )
        tampered = copy.deepcopy(event)
        tampered["physics_expectation"]["thermal"]["thermal_load_ratio"] += 0.5
        check, _ = verify_recorded_event(self.system, self.state, tampered)
        self.assertFalse(check["valid"])
        self.assertFalse(check["physics_matches"])


if __name__ == "__main__":
    unittest.main()
