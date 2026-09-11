from __future__ import annotations

import json
import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import axm_star_sim.io as runtime_io
from axm_star_sim.atlas import create_revisit_packet, import_normalized_catalog
from axm_star_sim.cli import main
from axm_star_sim.generator import generate_system
from axm_star_sim.io import (
    ATLAS_COMMIT_NAME,
    RuntimeCommitError,
    atlas_mutation_transaction,
    recover_atlas_commit,
    write_system,
)


class AtlasMutationRecoveryTests(unittest.TestCase):
    def _output(self, root: Path, seed: str) -> Path:
        output = root / "adventure"
        write_system(output, generate_system(seed).to_dict())
        return output

    def _run(self, *arguments: str) -> int:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return main(list(arguments))

    def test_interrupted_projection_recovers_exact_catalog_mutation(self):
        with TemporaryDirectory() as temp:
            output = self._output(Path(temp), "AXM-ATLAS-COMMIT-CATALOG")
            manifest_before = (output / "manifest.json").read_bytes()
            snapshot = {
                "schema": "axm.normalized-atlas-catalog.v1",
                "snapshot_id": "recoverable-catalog",
                "source_ids": ["esa_gaia"],
                "records": [],
            }
            with atlas_mutation_transaction(output) as transaction:
                atlas_after, _report = import_normalized_catalog(transaction.atlas, snapshot)
                with patch.object(runtime_io, "_write_manifest", side_effect=OSError("injected stop")):
                    with self.assertRaises(OSError):
                        transaction.commit(atlas_after)

            self.assertTrue((output / ATLAS_COMMIT_NAME).exists())
            self.assertEqual((output / "manifest.json").read_bytes(), manifest_before)
            self.assertEqual(self._run("atlas-status", "--output", str(output)), 1)
            self.assertEqual(self._run("recover-atlas", "--output", str(output)), 0)
            self.assertFalse((output / ATLAS_COMMIT_NAME).exists())
            atlas = json.loads((output / "expedition_atlas.json").read_text(encoding="utf-8"))
            self.assertEqual(atlas["catalog_revisions"][-1]["source_snapshot_id"], "recoverable-catalog")
            self.assertEqual(
                json.loads((output / "manifest.json").read_text(encoding="utf-8")),
                runtime_io._manifest_for(output),
            )
            self.assertEqual(self._run("atlas-status", "--output", str(output)), 0)

    def test_interrupted_revisit_recovers_packet_and_atlas_together(self):
        with TemporaryDirectory() as temp:
            output = self._output(Path(temp), "AXM-ATLAS-COMMIT-REVISIT")
            atlas_before = json.loads((output / "expedition_atlas.json").read_text(encoding="utf-8"))
            with atlas_mutation_transaction(output) as transaction:
                packet, atlas_after = create_revisit_packet(
                    transaction.atlas,
                    transaction.atlas["active_location_id"],
                    "recovery-test-engine",
                    created_at="2026-09-11T00:00:00+00:00",
                )
                with patch.object(runtime_io, "write_atlas_files", side_effect=OSError("injected stop")):
                    with self.assertRaises(OSError):
                        transaction.commit(atlas_after, revisit_packet=packet)

            packet_path = output / "revisit_packets" / f"{packet['packet_id']}.json"
            self.assertTrue(packet_path.exists())
            self.assertTrue((output / ATLAS_COMMIT_NAME).exists())
            self.assertEqual(
                json.loads((output / "expedition_atlas.json").read_text(encoding="utf-8")),
                atlas_before,
            )

            recover_atlas_commit(output)
            recovered_atlas = json.loads((output / "expedition_atlas.json").read_text(encoding="utf-8"))
            self.assertEqual(recovered_atlas, atlas_after)
            self.assertEqual(json.loads(packet_path.read_text(encoding="utf-8")), packet)
            self.assertFalse((output / ATLAS_COMMIT_NAME).exists())

    def test_recovery_refuses_divergent_atlas_and_preserves_commit(self):
        with TemporaryDirectory() as temp:
            output = self._output(Path(temp), "AXM-ATLAS-COMMIT-DIVERGENCE")
            with atlas_mutation_transaction(output) as transaction:
                packet, atlas_after = create_revisit_packet(
                    transaction.atlas,
                    transaction.atlas["active_location_id"],
                    "divergence-test-engine",
                    created_at="2026-09-11T00:00:00+00:00",
                )
                with patch.object(runtime_io, "write_atlas_files", side_effect=OSError("injected stop")):
                    with self.assertRaises(OSError):
                        transaction.commit(atlas_after, revisit_packet=packet)

            atlas_path = output / "expedition_atlas.json"
            divergent = json.loads(atlas_path.read_text(encoding="utf-8"))
            divergent["updated_at"] = "foreign-change"
            atlas_path.write_text(json.dumps(divergent), encoding="utf-8")
            with self.assertRaises(RuntimeCommitError):
                recover_atlas_commit(output)
            self.assertTrue((output / ATLAS_COMMIT_NAME).exists())


if __name__ == "__main__":
    unittest.main()
