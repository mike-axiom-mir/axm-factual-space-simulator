import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from axm_star_sim.catalog import (
    build_jpl_sbdb_url,
    build_nasa_exoplanet_archive_url,
    normalize_nasa_snapshot,
    summarize_catalog,
)
from axm_star_sim.generator import generate_system
from axm_star_sim.io import write_system
from axm_star_sim.validation import validate_system


class GeneratorTests(unittest.TestCase):
    def canonical(self, seed: str):
        data = generate_system(seed).to_dict()
        data["generated_at"] = "<excluded>"
        return data

    def test_same_seed_is_deterministic(self):
        self.assertEqual(self.canonical("AXM-SAME"), self.canonical("AXM-SAME"))

    def test_different_seed_changes_system(self):
        self.assertNotEqual(
            self.canonical("AXM-A")["system_id"],
            self.canonical("AXM-B")["system_id"],
        )

    def test_truth_layer_validation(self):
        data = self.canonical("AXM-TRUTH")
        warnings = validate_system(data)
        self.assertIsInstance(warnings, list)
        for evidence in data["star"].values():
            if evidence["truth_type"] == "derived":
                self.assertTrue(evidence["formula_id"])
        for planet in data["planets"]:
            for evidence in planet["facts"].values():
                if evidence["truth_type"] == "derived":
                    self.assertTrue(evidence["formula_id"])


    def test_all_evidence_sources_are_registered(self):
        data = self.canonical("AXM-SOURCES")
        known = set(data["source_registry"]["sources"])
        for evidence in data["star"].values():
            self.assertFalse(set(evidence["source_ids"]) - known)
        for planet in data["planets"]:
            for evidence in planet["facts"].values():
                self.assertFalse(set(evidence["source_ids"]) - known)

    def test_orbits_are_ordered(self):
        data = self.canonical("AXM-ORBITS")
        axes = [p["facts"]["semi_major_axis"]["value"] for p in data["planets"]]
        self.assertEqual(axes, sorted(axes))


    def test_catalog_pipeline_with_pinned_mock_snapshot(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            snap = root / "snapshot"
            snap.mkdir()
            rows = [
                {
                    "pl_name": "AXM Test b", "hostname": "AXM Test", "disc_year": 2026,
                    "discoverymethod": "Transit", "pl_orbper": 12.5, "pl_orbsmax": 0.11,
                    "pl_rade": 1.2, "pl_bmasse": 2.1, "st_teff": 5100, "st_mass": 0.82,
                },
                {
                    "pl_name": "AXM Test c", "hostname": "AXM Test", "disc_year": 2026,
                    "discoverymethod": "Transit", "pl_orbper": 31.0, "pl_orbsmax": 0.21,
                    "pl_rade": 2.4, "st_teff": 5100, "st_mass": 0.82,
                },
            ]
            raw = json.dumps(rows).encode("utf-8")
            import hashlib
            (snap / "raw.json").write_bytes(raw)
            (snap / "normalized.json").write_bytes(raw)
            (snap / "manifest.json").write_text(json.dumps({
                "sha256": hashlib.sha256(raw).hexdigest(),
                "retrieved_at": "2026-08-02T00:00:00+00:00",
            }))
            normalized = root / "catalog.jsonl"
            manifest = normalize_nasa_snapshot(snap, normalized)
            self.assertEqual(manifest["records"], 2)
            summary = summarize_catalog(normalized, root / "summary.json")
            self.assertEqual(summary["records"], 2)
            self.assertFalse(summary["automatic_generator_authority"])
            self.assertEqual(summary["fields"]["orbital_period"]["median"], 21.75)

    def test_source_urls_are_bounded_and_encoded(self):
        nasa = build_nasa_exoplanet_archive_url(25)
        self.assertIn("pscomppars", nasa)
        self.assertIn("top+25", nasa)
        jpl = build_jpl_sbdb_url("433 Eros")
        self.assertIn("433+Eros", jpl)
        with self.assertRaises(ValueError):
            build_nasa_exoplanet_archive_url(0)

    def test_output_package(self):
        data = generate_system("AXM-OUTPUT").to_dict()
        with TemporaryDirectory() as temp:
            out = Path(temp)
            manifest = write_system(out, data)
            for name in ["system.json", "causality_log.jsonl", "system.html", "manifest.json"]:
                self.assertTrue((out / name).exists())
            self.assertIn("system.html", manifest["files"])
            self.assertIn("AXM factual star adventure simulator", (out / "system.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
