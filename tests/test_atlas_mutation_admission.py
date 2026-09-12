from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import axm_star_sim.io as runtime_io
from axm_star_sim.cli import main
from axm_star_sim.generator import generate_system
from axm_star_sim.io import RUNTIME_COMMIT_NAME, append_runtime_event, write_system
from axm_star_sim.runtime import resolve_turn


LOCK_HOLDER = r"""
import sys
import time
from pathlib import Path

from axm_star_sim.storage import output_mutation_lock

output = Path(sys.argv[1])
ready = Path(sys.argv[2])
release = Path(sys.argv[3])
with output_mutation_lock(output):
    ready.write_text("owned", encoding="utf-8")
    while not release.exists():
        time.sleep(0.01)
"""


class AtlasMutationAdmissionTests(unittest.TestCase):
    def _run(self, *arguments: str) -> int:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return main(list(arguments))

    def _write_catalog_snapshot(self, path: Path) -> None:
        snapshot = {
            "schema": "axm.normalized-atlas-catalog.v1",
            "snapshot_id": "atlas-admission-fixture",
            "source_ids": ["esa_gaia"],
            "records": [],
        }
        path.write_text(json.dumps(snapshot), encoding="utf-8")

    def _lock_holder(self, output: Path, scratch: Path) -> tuple[subprocess.Popen, Path]:
        ready = scratch / "ready"
        release = scratch / "release"
        environment = os.environ.copy()
        source = str(Path(__file__).resolve().parents[1] / "src")
        environment["PYTHONPATH"] = source + os.pathsep + environment.get("PYTHONPATH", "")
        process = subprocess.Popen(
            [sys.executable, "-c", LOCK_HOLDER, str(output), str(ready), str(release)],
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

    def test_atlas_only_commands_refuse_an_output_owned_by_another_mutator(self):
        commands = ("atlas-import-system", "revisit-location", "atlas-import-catalog")
        for command in commands:
            with self.subTest(command=command), TemporaryDirectory() as temp:
                root = Path(temp)
                output = root / "adventure"
                system = generate_system(f"AXM-ATLAS-LOCK-{command}").to_dict()
                write_system(output, system)
                atlas_before = (output / "expedition_atlas.json").read_bytes()
                manifest_before = (output / "manifest.json").read_bytes()

                if command == "atlas-import-system":
                    imported = root / "imported-system.json"
                    imported.write_text(
                        json.dumps(generate_system("AXM-ATLAS-LOCK-IMPORTED").to_dict()),
                        encoding="utf-8",
                    )
                    arguments = (
                        command,
                        "--output",
                        str(output),
                        "--system-json",
                        str(imported),
                    )
                elif command == "revisit-location":
                    atlas = json.loads(atlas_before)
                    arguments = (
                        command,
                        "--output",
                        str(output),
                        "--location-id",
                        atlas["active_location_id"],
                        "--visual-engine-version",
                        "atlas-admission-test",
                    )
                else:
                    snapshot = root / "snapshot.json"
                    self._write_catalog_snapshot(snapshot)
                    arguments = (
                        command,
                        "--output",
                        str(output),
                        "--snapshot",
                        str(snapshot),
                    )

                process, release = self._lock_holder(output, root)
                try:
                    self.assertEqual(self._run(*arguments), 1)
                finally:
                    release.write_text("release", encoding="utf-8")
                    process.wait(timeout=10)
                self.assertEqual(process.returncode, 0)

                self.assertEqual((output / "expedition_atlas.json").read_bytes(), atlas_before)
                self.assertEqual((output / "manifest.json").read_bytes(), manifest_before)
                self.assertFalse((output / "revisit_packets").exists())

    def test_atlas_mutation_recovers_a_sealed_runtime_commit_before_reading(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "adventure"
            system = generate_system("AXM-ATLAS-RECOVERY-ADMISSION").to_dict()
            write_system(output, system)
            state = json.loads((output / "runtime_state.json").read_text(encoding="utf-8"))
            event, updated = resolve_turn(
                system=system,
                state=state,
                action="1",
                entropy_mode="deterministic",
            )
            with patch.object(runtime_io, "_atomic_write_ledger", side_effect=OSError("injected stop")):
                with self.assertRaises(OSError):
                    append_runtime_event(output, event, updated)
            self.assertTrue((output / RUNTIME_COMMIT_NAME).exists())

            snapshot = root / "snapshot.json"
            self._write_catalog_snapshot(snapshot)
            self.assertEqual(
                self._run(
                    "atlas-import-catalog",
                    "--output",
                    str(output),
                    "--snapshot",
                    str(snapshot),
                ),
                0,
            )

            atlas = json.loads((output / "expedition_atlas.json").read_text(encoding="utf-8"))
            self.assertEqual(atlas["visits"][-1]["event_hash"], event["event_hash"])
            self.assertEqual(atlas["catalog_revisions"][-1]["source_snapshot_id"], "atlas-admission-fixture")
            self.assertFalse((output / RUNTIME_COMMIT_NAME).exists())

    def test_atlas_mutation_refuses_an_invalid_existing_visit_chain(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "adventure"
            write_system(output, generate_system("AXM-ATLAS-INVALID-CHAIN").to_dict())
            atlas_path = output / "expedition_atlas.json"
            atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
            atlas["visits"][0]["note"] = "silently rewritten"
            atlas_path.write_text(json.dumps(atlas), encoding="utf-8")
            before = atlas_path.read_bytes()

            snapshot = root / "snapshot.json"
            self._write_catalog_snapshot(snapshot)
            self.assertEqual(
                self._run(
                    "atlas-import-catalog",
                    "--output",
                    str(output),
                    "--snapshot",
                    str(snapshot),
                ),
                1,
            )
            self.assertEqual(atlas_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
