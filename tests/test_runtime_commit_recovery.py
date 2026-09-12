from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import axm_star_sim.io as runtime_io
from axm_star_sim.atlas import verify_visit_chain
from axm_star_sim.generator import generate_system
from axm_star_sim.io import (
    RUNTIME_COMMIT_NAME,
    RuntimeCommitError,
    append_runtime_event,
    load_ledger,
    recover_runtime_commit,
    sha256_file,
    write_system,
)
from axm_star_sim.runtime import canonical_hash, resolve_turn, verify_ledger


class RuntimeCommitRecoveryTests(unittest.TestCase):
    def _prepared_turn(self, output: Path):
        system = generate_system("AXM-RUNTIME-COMMIT-RECOVERY").to_dict()
        write_system(output, system)
        state = json.loads((output / "runtime_state.json").read_text(encoding="utf-8"))
        event, updated = resolve_turn(
            system=system,
            state=state,
            action="1",
            entropy_mode="deterministic",
        )
        return system, state, event, updated

    def _assert_recovered(self, output: Path, system: dict, event: dict, expected_state: dict) -> None:
        events = load_ledger(output / "event_ledger.jsonl")
        commands = load_ledger(output / "command_ledger.jsonl")
        self.assertEqual([row["event_hash"] for row in events], [event["event_hash"]])
        self.assertEqual([row["event_hash"] for row in commands], [event["event_hash"]])
        valid, checks, rebuilt = verify_ledger(system, events)
        self.assertTrue(valid, checks)
        self.assertEqual(canonical_hash(rebuilt), canonical_hash(expected_state))
        state = json.loads((output / "runtime_state.json").read_text(encoding="utf-8"))
        self.assertEqual(canonical_hash(state), canonical_hash(expected_state))
        atlas = json.loads((output / "expedition_atlas.json").read_text(encoding="utf-8"))
        self.assertTrue(verify_visit_chain(atlas)["valid"])
        self.assertEqual(atlas["visits"][-1]["event_hash"], event["event_hash"])
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        for name, digest in manifest["files"].items():
            self.assertEqual(sha256_file(output / name), digest, name)
        self.assertFalse((output / RUNTIME_COMMIT_NAME).exists())

    def test_recovery_finishes_commit_when_event_write_never_started(self):
        with TemporaryDirectory() as temp:
            output = Path(temp)
            system, _before, event, updated = self._prepared_turn(output)
            with patch.object(runtime_io, "_atomic_write_ledger", side_effect=OSError("injected stop")):
                with self.assertRaises(OSError):
                    append_runtime_event(output, event, updated)
            self.assertEqual(load_ledger(output / "event_ledger.jsonl"), [])
            self.assertTrue((output / RUNTIME_COMMIT_NAME).exists())
            recover_runtime_commit(output)
            self._assert_recovered(output, system, event, updated)
            self.assertIsNone(recover_runtime_commit(output))

    def test_recovery_rebuilds_projections_after_canonical_event_commit(self):
        with TemporaryDirectory() as temp:
            output = Path(temp)
            system, _before, event, updated = self._prepared_turn(output)
            original = runtime_io._atomic_write_ledger
            calls = 0

            def stop_before_command_projection(path, records):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected stop")
                return original(path, records)

            with patch.object(runtime_io, "_atomic_write_ledger", side_effect=stop_before_command_projection):
                with self.assertRaises(OSError):
                    append_runtime_event(output, event, updated)
            self.assertEqual(len(load_ledger(output / "event_ledger.jsonl")), 1)
            self.assertEqual(load_ledger(output / "command_ledger.jsonl"), [])
            self.assertTrue((output / RUNTIME_COMMIT_NAME).exists())
            recover_runtime_commit(output)
            self._assert_recovered(output, system, event, updated)

    def test_retry_does_not_duplicate_an_already_written_atlas_visit(self):
        with TemporaryDirectory() as temp:
            output = Path(temp)
            system, _before, event, updated = self._prepared_turn(output)
            with patch.object(runtime_io, "_refresh_consoles", side_effect=OSError("injected stop")):
                with self.assertRaises(OSError):
                    append_runtime_event(output, event, updated)
            atlas = json.loads((output / "expedition_atlas.json").read_text(encoding="utf-8"))
            self.assertEqual(sum(row.get("event_hash") == event["event_hash"] for row in atlas["visits"]), 1)
            recover_runtime_commit(output)
            self._assert_recovered(output, system, event, updated)
            atlas = json.loads((output / "expedition_atlas.json").read_text(encoding="utf-8"))
            self.assertEqual(sum(row.get("event_hash") == event["event_hash"] for row in atlas["visits"]), 1)

    def test_recovery_refuses_altered_intent_and_divergent_history(self):
        with TemporaryDirectory() as temp:
            output = Path(temp)
            _system, _before, event, updated = self._prepared_turn(output)
            with patch.object(runtime_io, "_atomic_write_ledger", side_effect=OSError("injected stop")):
                with self.assertRaises(OSError):
                    append_runtime_event(output, event, updated)
            journal_path = output / RUNTIME_COMMIT_NAME
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            journal["state_after"]["turn"] += 1
            journal_path.write_text(json.dumps(journal), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeCommitError, "seal is invalid"):
                recover_runtime_commit(output)
            self.assertTrue(journal_path.exists())

        with TemporaryDirectory() as temp:
            output = Path(temp)
            _system, _before, event, updated = self._prepared_turn(output)
            original = runtime_io._atomic_write_ledger
            calls = 0

            def stop_after_event(path, records):
                nonlocal calls
                calls += 1
                result = original(path, records)
                if calls == 1:
                    raise OSError("injected stop")
                return result

            with patch.object(runtime_io, "_atomic_write_ledger", side_effect=stop_after_event):
                with self.assertRaises(OSError):
                    append_runtime_event(output, event, updated)
            with (output / "event_ledger.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"event_id": "foreign-history"}) + "\n")
            with self.assertRaisesRegex(RuntimeCommitError, "diverged"):
                recover_runtime_commit(output)
            self.assertTrue((output / RUNTIME_COMMIT_NAME).exists())

    def test_event_and_state_are_verified_before_commit_is_sealed(self):
        with TemporaryDirectory() as temp:
            output = Path(temp)
            _system, before, event, _updated = self._prepared_turn(output)
            with self.assertRaisesRegex(RuntimeCommitError, "state does not match"):
                append_runtime_event(output, event, before)
            self.assertEqual(load_ledger(output / "event_ledger.jsonl"), [])
            self.assertFalse((output / RUNTIME_COMMIT_NAME).exists())


if __name__ == "__main__":
    unittest.main()
