import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from axm_star_sim.entropy import (
    create_commitment,
    create_master_seed_receipt,
    resolve_entropy,
    roll,
    verify_reveal,
)
from axm_star_sim.generator import generate_system
from axm_star_sim.io import append_runtime_event, load_ledger, write_system
from axm_star_sim.runtime import initial_runtime_state, resolve_turn, verify_recorded_event


class OpenFutureTests(unittest.TestCase):
    def system(self):
        return generate_system("AXM-OPEN-FUTURE-TEST").to_dict()

    def test_deterministic_event_is_replayable(self):
        system = self.system()
        state = initial_runtime_state(system)
        event_a, state_a = resolve_turn(system=system, state=state, action="1", entropy_mode="deterministic")
        event_b, state_b = resolve_turn(
            system=system,
            state=state,
            action="1",
            entropy_mode="deterministic",
            replay_entropy=event_a["entropy"],
        )
        self.assertEqual(event_a["rolls"], event_b["rolls"])
        self.assertEqual(event_a["outcome"]["id"], event_b["outcome"]["id"])
        self.assertTrue(event_a["predetermined_by_master_seed"])
        self.assertEqual(state_a["resources"], state_b["resources"])

    def test_local_live_is_not_derived_from_master_seed(self):
        context = {"event": "same"}
        first = resolve_entropy(mode="local_live", master_seed="SAME", context=context)
        second = resolve_entropy(mode="local_live", master_seed="SAME", context=context)
        self.assertFalse(first.predetermined_by_master_seed)
        self.assertNotEqual(first.combined_sha256, second.combined_sha256)
        self.assertIn("local_os_token_hex", first.replay_material)

    def test_mixed_live_preserves_context_and_adds_live_entropy(self):
        context = {"event": "same"}
        packet = resolve_entropy(mode="mixed_live", master_seed="SAME", context=context)
        self.assertFalse(packet.predetermined_by_master_seed)
        self.assertIn("deterministic_component", packet.replay_material)
        self.assertIn("local_os_token_hex", packet.replay_material)
        self.assertGreaterEqual(roll(packet, "outcome"), 0)
        self.assertLessEqual(roll(packet, "outcome"), 1)

    def test_external_beacon_requires_real_provider_verification(self):
        with self.assertRaises(ValueError):
            resolve_entropy(
                mode="external_beacon",
                master_seed="SAME",
                context={"event": 1},
                beacon={"provider": "test", "round": 42, "randomness": "ab" * 32, "signature": "sig"},
            )

    def test_party_commit_reveal(self):
        mike = create_commitment("Mike", "alpha")
        axiom = create_commitment("Axiom", "beta")
        self.assertTrue(verify_reveal(mike))
        packet = resolve_entropy(
            mode="party_commit",
            master_seed="SAME",
            context={"event": 1},
            party_reveals=[mike, axiom],
        )
        self.assertFalse(packet.predetermined_by_master_seed)
        self.assertEqual(len(packet.replay_material["party_reveals"]), 2)
        broken = dict(mike)
        broken["value"] = "changed"
        with self.assertRaises(ValueError):
            resolve_entropy(
                mode="party_commit",
                master_seed="SAME",
                context={"event": 1},
                party_reveals=[broken, axiom],
            )

    def test_live_master_seed_receipt(self):
        first = create_master_seed_receipt("local_live")
        second = create_master_seed_receipt("local_live")
        self.assertNotEqual(first["resolved_seed"], second["resolved_seed"])
        self.assertTrue(first["resolved_seed"].startswith("AXM-"))

    def test_action_is_part_of_future_context(self):
        system = self.system()
        state = initial_runtime_state(system)
        first, _ = resolve_turn(system=system, state=state, action="1", entropy_mode="deterministic")
        second, _ = resolve_turn(system=system, state=state, action="2", entropy_mode="deterministic")
        self.assertNotEqual(first["entropy"]["context_sha256"], second["entropy"]["context_sha256"])

    def test_tampered_event_is_rejected(self):
        system = self.system()
        state = initial_runtime_state(system)
        event, _ = resolve_turn(system=system, state=state, action="1", entropy_mode="deterministic")
        event["outcome"]["id"] = "silently-rewritten"
        check, _ = verify_recorded_event(system, state, event)
        self.assertFalse(check["valid"])
        self.assertFalse(check["recorded_event_hash_valid"])
        self.assertFalse(check["outcome_matches"])

    def test_hash_chained_ledger_verifies(self):
        system = self.system()
        with TemporaryDirectory() as temp:
            output = Path(temp)
            write_system(output, system)
            state = json.loads((output / "runtime_state.json").read_text(encoding="utf-8"))
            for action, mode in [("1", "mixed_live"), ("2", "local_live")]:
                event, state = resolve_turn(system=system, state=state, action=action, entropy_mode=mode)
                append_runtime_event(output, event, state)
            replay_state = initial_runtime_state(system)
            for event in load_ledger(output / "event_ledger.jsonl"):
                check, replay_state = verify_recorded_event(system, replay_state, event)
                self.assertTrue(check["valid"], check)
            self.assertIn("crypto.getRandomValues", (output / "adventure_console.html").read_text(encoding="utf-8"))
            self.assertEqual(len(load_ledger(output / "event_ledger.jsonl")), 2)


if __name__ == "__main__":
    unittest.main()
