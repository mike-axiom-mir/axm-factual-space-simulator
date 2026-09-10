from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from axm_star_sim.command import plan_command, proposal
from axm_star_sim.generator import generate_system
from axm_star_sim.io import (
    RUNTIME_COMMIT_NAME,
    append_runtime_event,
    load_ledger,
    load_pending_session,
    save_pending_session,
    write_system,
)
from axm_star_sim.runtime import resolve_turn
from axm_star_sim.storage import OutputMutationBusy, output_mutation_lock


HOLDER = r"""
import os
import sys
import time
from pathlib import Path

from axm_star_sim.storage import output_mutation_lock

output = Path(sys.argv[1])
ready = Path(sys.argv[2])
release = Path(sys.argv[3])
with output_mutation_lock(output):
    ready.write_text(str(os.getpid()), encoding="utf-8")
    while not release.exists():
        time.sleep(0.01)
"""


class RuntimeSingleWriterTests(unittest.TestCase):
    def _prepared_turn(self, output: Path):
        system = generate_system("AXM-RUNTIME-SINGLE-WRITER").to_dict()
        write_system(output, system, "collaborative_command")
        state = json.loads((output / "runtime_state.json").read_text(encoding="utf-8"))
        event, updated = resolve_turn(
            system=system,
            state=state,
            action="1",
            entropy_mode="deterministic",
        )
        actions = system["adventure"]["selected_opportunity"]["actions"]
        session = plan_command(
            system=system,
            state=state,
            mode="collaborative_command",
            human_proposal=proposal("human", actions[0]),
            ai_proposal=proposal("ai", actions[1]),
        )["session"]
        return event, updated, state, session

    def _holder(self, output: Path, scratch: Path):
        ready = scratch / "ready"
        release = scratch / "release"
        environment = os.environ.copy()
        source = str(Path(__file__).resolve().parents[1] / "src")
        environment["PYTHONPATH"] = source + os.pathsep + environment.get("PYTHONPATH", "")
        process = subprocess.Popen(
            [sys.executable, "-c", HOLDER, str(output), str(ready), str(release)],
            env=environment,
        )
        deadline = time.monotonic() + 10
        while not ready.exists():
            if process.poll() is not None:
                self.fail(f"lock holder exited early with {process.returncode}")
            if time.monotonic() >= deadline:
                process.kill()
                self.fail("lock holder did not acquire the output mutation lock")
            time.sleep(0.01)
        return process, release

    def test_other_process_cannot_commit_or_replace_pending_state(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "adventure"
            event, updated, state, session = self._prepared_turn(output)
            process, release = self._holder(output, root)
            try:
                with self.assertRaisesRegex(OutputMutationBusy, "another local process"):
                    append_runtime_event(output, event, updated)
                with self.assertRaisesRegex(OutputMutationBusy, "another local process"):
                    save_pending_session(output, session, state)
                self.assertEqual(load_ledger(output / "event_ledger.jsonl"), [])
                self.assertIsNone(load_pending_session(output))
                self.assertFalse((output / RUNTIME_COMMIT_NAME).exists())
            finally:
                release.write_text("release", encoding="utf-8")
                process.wait(timeout=10)
            self.assertEqual(process.returncode, 0)

    def test_abrupt_holder_exit_releases_kernel_owned_lock(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "adventure"
            event, updated, _state, _session = self._prepared_turn(output)
            process, _release = self._holder(output, root)
            process.kill()
            process.wait(timeout=10)

            manifest = append_runtime_event(output, event, updated)
            self.assertEqual(len(load_ledger(output / "event_ledger.jsonl")), 1)
            self.assertIn("event_ledger.jsonl", manifest["files"])

    def test_same_process_can_use_explicit_coordination_boundary(self):
        with TemporaryDirectory() as temp:
            output = Path(temp)
            with output_mutation_lock(output):
                self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
