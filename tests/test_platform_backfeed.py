from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_platform_backfeed as builder  # noqa: E402
import install_platform_backfeed as installer  # noqa: E402


class PlatformBackfeedTests(unittest.TestCase):
    def test_capsule_build_is_deterministic_and_dependency_free(self) -> None:
        with tempfile.TemporaryDirectory() as first_temp, tempfile.TemporaryDirectory() as second_temp:
            first_root = Path(first_temp) / "dist"
            second_root = Path(second_temp) / "dist"
            first = builder.build_capsule(first_root)
            second = builder.build_capsule(second_root)
            self.assertEqual(first, second)
            self.assertEqual(builder.tree_inventory(first_root), builder.tree_inventory(second_root))
            self.assertEqual(first["schema"], builder.CAPSULE_SCHEMA)
            self.assertEqual(len(first["modules"]), 3)
            self.assertTrue(all(row["external_dependencies"] == [] for row in first["modules"]))
            self.assertFalse(first["policy"]["automatic_install_allowed"])
            self.assertFalse(first["policy"]["automatic_promotion_allowed"])

    def test_generated_dist_matches_sources(self) -> None:
        result = builder.check_dist()
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["module_count"], 3)

    def test_javascript_module_selftests(self) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is unavailable")
        modules = ROOT / "platform_backfeed" / "source" / "modules"
        for module_id in ("deterministic-json-core", "immutable-history-guard", "branch-backfeed-lab"):
            completed = subprocess.run(
                [node, "selftest.js"], cwd=modules / module_id,
                text=True, encoding="utf-8", errors="replace",
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertIn("PASS", completed.stdout)

    def test_hub_signal_fails_closed_on_hold(self) -> None:
        app = (ROOT / "platform_backfeed" / "source" / "modules" / "branch-backfeed-lab" / "app.js").read_text(encoding="utf-8")
        gate = app.index("receipt.verdict === 'READY_FOR_GRAFT'")
        pass_signal = app.index("type: 'hub:verify:pass'")
        error_signal = app.index("type: 'hub:error'")
        self.assertLess(gate, pass_signal)
        self.assertLess(pass_signal, error_signal)
        self.assertIn("Capsule held:", app)

    def test_plan_apply_installs_only_new_leaf_modules(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workshop = Path(temporary) / "workshop"
            (workshop / "tools").mkdir(parents=True)
            (workshop / "hub").mkdir()
            (workshop / "hub" / "module-contract-verifier.js").write_text("module.exports = {};\n", encoding="utf-8")
            (workshop / "hub" / "graft-core.js").write_text("module.exports = {};\n", encoding="utf-8")
            plan = installer.build_plan(workshop)
            self.assertTrue(all(not row["target_exists"] for row in plan["targets"]))
            receipt = installer.apply_plan(workshop, plan["plan_digest"])
            self.assertEqual(receipt["schema"], "axm.branch-backfeed-install-receipt/v1")
            self.assertFalse(receipt["registry_changed"])
            self.assertFalse(receipt["promoted"])
            self.assertEqual(len(receipt["installed"]), 3)
            for row in receipt["installed"]:
                target = Path(row["target"])
                self.assertTrue((target / "manifest.json").is_file())
                self.assertTrue((target / "module.contract.json").is_file())
            receipt_data = json.loads(Path(receipt["receipt_path"]).read_text(encoding="utf-8"))
            self.assertEqual(receipt_data["plan_digest"], plan["plan_digest"])
            changed_plan = installer.build_plan(workshop)
            self.assertTrue(all(row["target_exists"] for row in changed_plan["targets"]))
            self.assertNotEqual(changed_plan["plan_digest"], plan["plan_digest"])
            with self.assertRaises(ValueError):
                installer.apply_plan(workshop, plan["plan_digest"])


if __name__ == "__main__":
    unittest.main()
