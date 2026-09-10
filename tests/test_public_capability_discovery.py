from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "tools" / "generate_public_capabilities.py"
SPEC = importlib.util.spec_from_file_location("axm_public_capability_generator", GENERATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
GEN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GEN)


class PublicCapabilityDiscoveryTests(unittest.TestCase):
    def fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        for relative in GEN.SOURCE_PATHS:
            source = ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return temp, root

    def test_committed_generated_outputs_are_exact(self) -> None:
        GEN.verify_outputs(ROOT)
        record = json.loads((ROOT / GEN.REGISTRY_PATH).read_text("utf-8"))
        self.assertEqual(record["schema"], "axm.public-capability/v1")
        self.assertEqual(record["id"], GEN.CAPABILITY_ID)
        self.assertIsNone(record["status"])
        self.assertEqual(record["runtime"]["dependencies"], [])
        self.assertFalse(record["runtime"]["networkRequired"])
        self.assertFalse(record["runtime"]["accountRequired"])
        self.assertEqual(record["operations"], ["generate", "verify-ledger"])
        self.assertTrue(record["authority"]["discoveryOnly"])
        for field in ("execution", "automaticInstall", "automaticSelection", "packagePublication", "release", "merge", "canon"):
            self.assertFalse(record["authority"][field])

    def test_public_marker_drift_fails_closed(self) -> None:
        temp, root = self.fixture()
        self.addCleanup(temp.cleanup)
        marker_path = root / ".axm" / "discovery-public.json"
        marker = json.loads(marker_path.read_text("utf-8"))
        marker["public"] = False
        marker_path.write_text(json.dumps(marker), encoding="utf-8")
        with self.assertRaisesRegex(GEN.DiscoveryContractError, "explicit review") as caught:
            GEN.build_capability(root)
        self.assertEqual(caught.exception.code, "PUBLIC_MARKER_DRIFT")

    def test_package_version_drift_requires_review(self) -> None:
        temp, root = self.fixture()
        self.addCleanup(temp.cleanup)
        path = root / "pyproject.toml"
        text = path.read_text("utf-8").replace('version = "0.15.0"', 'version = "0.16.0"', 1)
        path.write_text(text, encoding="utf-8")
        with self.assertRaises(GEN.DiscoveryContractError) as caught:
            GEN.build_capability(root)
        self.assertEqual(caught.exception.code, "PACKAGE_IDENTITY_DRIFT")

    def test_runtime_dependency_widening_requires_review(self) -> None:
        temp, root = self.fixture()
        self.addCleanup(temp.cleanup)
        path = root / "pyproject.toml"
        text = path.read_text("utf-8").replace("dependencies = []", 'dependencies = ["requests"]', 1)
        path.write_text(text, encoding="utf-8")
        with self.assertRaises(GEN.DiscoveryContractError) as caught:
            GEN.build_capability(root)
        self.assertEqual(caught.exception.code, "PACKAGE_DEPENDENCY_DRIFT")

    def test_required_cli_operation_removal_requires_review(self) -> None:
        temp, root = self.fixture()
        self.addCleanup(temp.cleanup)
        path = root / "src" / "axm_star_sim" / "cli.py"
        text = path.read_text("utf-8").replace('sub.add_parser("verify-ledger"', 'sub.add_parser("verify-ledger-removed"', 1)
        path.write_text(text, encoding="utf-8")
        with self.assertRaises(GEN.DiscoveryContractError) as caught:
            GEN.build_capability(root)
        self.assertEqual(caught.exception.code, "CLI_CONTRACT_DRIFT")

    def test_reproducible_builder_authority_widening_requires_review(self) -> None:
        temp, root = self.fixture()
        self.addCleanup(temp.cleanup)
        path = root / "tools" / "build_reproducible_wheel.py"
        text = path.read_text("utf-8").replace('"release": False', '"release": True', 1)
        path.write_text(text, encoding="utf-8")
        with self.assertRaises(GEN.DiscoveryContractError) as caught:
            GEN.build_capability(root)
        self.assertEqual(caught.exception.code, "REPRODUCIBLE_BUILD_CONTRACT_DRIFT")

    def test_license_drift_requires_review(self) -> None:
        temp, root = self.fixture()
        self.addCleanup(temp.cleanup)
        (root / "LICENSE").write_text("Different license\n", encoding="utf-8")
        with self.assertRaises(GEN.DiscoveryContractError) as caught:
            GEN.build_capability(root)
        self.assertEqual(caught.exception.code, "LICENSE_DRIFT")

    def test_generated_registry_tamper_fails_exact_verification(self) -> None:
        temp, root = self.fixture()
        self.addCleanup(temp.cleanup)
        GEN.write_outputs(root)
        registry = root / GEN.REGISTRY_PATH
        registry.write_bytes(registry.read_bytes() + b"{}\n")
        with self.assertRaises(GEN.DiscoveryContractError) as caught:
            GEN.verify_outputs(root)
        self.assertEqual(caught.exception.code, "GENERATED_OUTPUT_DRIFT")

    def test_receipt_binds_source_bytes_and_pattern_provenance(self) -> None:
        temp, root = self.fixture()
        self.addCleanup(temp.cleanup)
        GEN.write_outputs(root)
        receipt = json.loads((root / GEN.RECEIPT_PATH).read_text("utf-8"))
        self.assertEqual(receipt["schema"], "axm.public-capability-receipt/v1")
        self.assertEqual(receipt["pattern_provenance"]["source_repo"], "mike-axiom-mir/axm-anomaly-garden")
        self.assertEqual(receipt["pattern_provenance"]["source_pr"], 10)
        paths = {row["path"] for row in receipt["sources"]}
        self.assertEqual(paths, {path.as_posix() for path in GEN.SOURCE_PATHS})
        for row in receipt["sources"]:
            self.assertEqual(len(row["sha256"]), 64)
            self.assertEqual(len(row["git_blob_sha1"]), 40)
        self.assertFalse(receipt["authority"]["execution"])
        self.assertFalse(receipt["authority"]["installation"])
        self.assertFalse(receipt["authority"]["merge"])
        self.assertFalse(receipt["authority"]["canon"])


if __name__ == "__main__":
    unittest.main()
