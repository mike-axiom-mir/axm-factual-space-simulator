import json
import tempfile
import unittest
from pathlib import Path

from axm_star_sim.package_seal import build_manifest, check_seal, write_seal


ROOT = Path(__file__).resolve().parents[1]


class PackageSealTests(unittest.TestCase):
    def test_current_package_seal_matches(self):
        result = check_seal(ROOT)
        self.assertTrue(result["valid"], result)

    def test_reseal_is_deterministic_and_excludes_generated_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "output").mkdir()
            (root / ".git").mkdir()
            (root / "README.md").write_text("hello\n", encoding="utf-8")
            (root / "output" / "generated.json").write_text("{}\n", encoding="utf-8")
            (root / ".git" / "config").write_text("local metadata\n", encoding="utf-8")
            (root / "PACKAGE_MANIFEST.json").write_text(
                json.dumps({
                    "schema": "axm.package-manifest.v1",
                    "package": "TEST",
                    "version": "1",
                    "policy": "test fixture",
                    "managed_file_count": 0,
                    "files": {},
                }),
                encoding="utf-8",
            )
            (root / "CHECKSUMS.sha256").write_text("", encoding="utf-8")

            first = write_seal(root)
            first_manifest = (root / "PACKAGE_MANIFEST.json").read_bytes()
            first_checksums = (root / "CHECKSUMS.sha256").read_bytes()
            second = write_seal(root)

            self.assertTrue(first["valid"], first)
            self.assertTrue(second["valid"], second)
            self.assertEqual(first_manifest, (root / "PACKAGE_MANIFEST.json").read_bytes())
            self.assertEqual(first_checksums, (root / "CHECKSUMS.sha256").read_bytes())
            self.assertEqual(set(build_manifest(root)["files"]), {"README.md"})

    def test_reseal_excludes_linked_worktree_git_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "README.md").write_text("hello\n", encoding="utf-8")
            (root / ".git").write_text(
                "gitdir: /private/axm/.git/worktrees/factual-one\n",
                encoding="utf-8",
            )
            (root / "PACKAGE_MANIFEST.json").write_text(
                json.dumps({
                    "schema": "axm.package-manifest.v1",
                    "package": "TEST",
                    "version": "1",
                    "policy": "test fixture",
                    "managed_file_count": 0,
                    "files": {},
                }),
                encoding="utf-8",
            )
            (root / "CHECKSUMS.sha256").write_text("", encoding="utf-8")

            first = write_seal(root)
            first_manifest = (root / "PACKAGE_MANIFEST.json").read_bytes()
            first_checksums = (root / "CHECKSUMS.sha256").read_bytes()

            (root / ".git").write_text(
                "gitdir: C:/Users/mike/project/.git/worktrees/factual-two\n",
                encoding="utf-8",
            )
            unchanged_after_checkout_move = check_seal(root)
            second = write_seal(root)

            self.assertTrue(first["valid"], first)
            self.assertTrue(unchanged_after_checkout_move["valid"], unchanged_after_checkout_move)
            self.assertTrue(second["valid"], second)
            self.assertEqual(first_manifest, (root / "PACKAGE_MANIFEST.json").read_bytes())
            self.assertEqual(first_checksums, (root / "CHECKSUMS.sha256").read_bytes())
            self.assertEqual(set(build_manifest(root)["files"]), {"README.md"})


if __name__ == "__main__":
    unittest.main()
