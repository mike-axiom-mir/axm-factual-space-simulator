import copy
import json
import tempfile
import unittest
from pathlib import Path

from axm_star_sim.blind_forge import (
    BlindForgeError,
    forge_blind_scenario,
    resolve_blind_action,
    resolve_session_action,
    scan_public_bundle_for_private_leaks,
    verify_private_reveal,
    verify_session,
    write_blind_forge_session,
)
from axm_star_sim.generator import generate_system


class BlindForgeTests(unittest.TestCase):
    def setUp(self):
        self.system = generate_system("AXM-BLIND-WORLD-TEST").to_dict()
        self.private, self.public = forge_blind_scenario(self.system, "AXM-PRIVATE-FORGE-TEST")

    def test_public_bundle_contains_no_private_origin(self):
        self.assertEqual(scan_public_bundle_for_private_leaks(self.public, self.private), [])
        serialized = json.dumps(self.public)
        self.assertNotIn("private_simulation_truth", serialized)
        self.assertNotIn(self.private["private_simulation_truth"]["resolution_secret"], serialized)
        self.assertNotIn(self.private["reasoned_candidate_matrix"]["selected_candidate_id"], serialized)

    def test_commitment_proves_preplay_scenario(self):
        result = verify_private_reveal(self.private, self.public)
        self.assertTrue(result["valid"], result)
        tampered = copy.deepcopy(self.private)
        tampered["private_simulation_truth"]["traits"]["persistence"] += 0.01
        self.assertFalse(verify_private_reveal(tampered, self.public)["valid"])

    def test_player_action_returns_observation_not_origin(self):
        event, updated = resolve_blind_action(
            self.private,
            self.public,
            self.public["initial_state"],
            "broad_spectrum_survey",
            "ENTROPY-A",
        )
        self.assertFalse(event["private_origin_disclosed"])
        self.assertNotIn("origin_class", json.dumps(event))
        self.assertEqual(updated["turn"], 1)
        self.assertLessEqual(updated["evidence_stage"], 1)

    def test_single_action_cannot_jump_evidence_ladder(self):
        _event, updated = resolve_blind_action(
            self.private,
            self.public,
            self.public["initial_state"],
            "measure_chemical_complexity",
            "HIGH-SIGNAL-DOES-NOT-MATTER",
        )
        self.assertLessEqual(updated["evidence_stage"], 1)

    def test_same_hidden_scenario_action_and_entropy_replay_exactly(self):
        args = (self.private, self.public, self.public["initial_state"], "switch_instrument_family", "ENTROPY-B")
        first_event, first_state = resolve_blind_action(*args)
        second_event, second_state = resolve_blind_action(*args)
        self.assertEqual(first_event, second_event)
        self.assertEqual(first_state, second_state)

    def test_changed_entropy_can_change_measurement_without_rewriting_hidden_truth(self):
        strengths = {
            resolve_blind_action(
                self.private,
                self.public,
                self.public["initial_state"],
                "broad_spectrum_survey",
                f"ENTROPY-{i}",
            )[0]["observation"]["realized_pattern_strength"]
            for i in range(20)
        }
        self.assertGreater(len(strengths), 1)
        self.assertTrue(verify_private_reveal(self.private, self.public)["valid"])

    def test_session_replay_and_tamper_detection(self):
        state = copy.deepcopy(self.public["initial_state"])
        events = []
        tokens = ["T1", "T2", "T3"]
        for action, token in zip(
            ["broad_spectrum_survey", "repeat_changed_geometry", "abiotic_control_campaign"],
            tokens,
        ):
            event, state = resolve_blind_action(self.private, self.public, state, action, token)
            events.append(event)
        result = verify_session(self.private, self.public, events, tokens)
        self.assertTrue(result["valid"], result)
        tampered = copy.deepcopy(events)
        tampered[1]["observation"]["realized_pattern_strength"] += 0.1
        self.assertFalse(verify_session(self.private, self.public, tampered, tokens)["valid"])

    def test_private_mismatch_fails_closed(self):
        wrong_private, _wrong_public = forge_blind_scenario(self.system, "DIFFERENT-FORGE-SEED")
        with self.assertRaises(BlindForgeError):
            resolve_blind_action(
                wrong_private,
                self.public,
                self.public["initial_state"],
                "broad_spectrum_survey",
                "T1",
            )

    def test_filesystem_separation_and_host_resolution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_blind_forge_session(root, self.system, self.private, self.public)
            self.assertTrue((root / "forge_private" / "hidden_scenario.json").exists())
            self.assertTrue((root / "player_public" / "mission_bundle.json").exists())
            public_text = "\n".join(path.read_text(encoding="utf-8") for path in (root / "player_public").glob("*.*"))
            self.assertNotIn(self.private["private_simulation_truth"]["resolution_secret"], public_text)
            result = resolve_session_action(root, "broad_spectrum_survey", "HOST-TOKEN")
            self.assertEqual(result["state"]["turn"], 1)
            self.assertIn("Blind player view", (root / "player_public" / "player_console.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
