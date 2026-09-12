from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "output" / "contact_horizon_demo" / "contact_horizon_console.html"
RECEIPT = ROOT / "output" / "contact_horizon_demo" / "contact_horizon_demo.json"


class ContactHorizonExperienceTests(unittest.TestCase):
    def test_shipped_surface_exposes_readiness_and_authority_boundaries(self) -> None:
        page = HTML.read_text(encoding="utf-8")
        self.assertIn('role="tablist"', page)
        self.assertIn('aria-live="polite"', page)
        self.assertIn('SEARCH READINESS ≠ CONTACT', page)
        self.assertIn('DISPLAY ≠ DISCOVERY', page)
        self.assertIn('Readiness gate', page)
        self.assertIn('Next scientific move', page)
        self.assertIn("ArrowRight", page)
        self.assertIn("aria-selected", page)

    def test_surface_reuses_exact_recorded_claim_and_action_truth(self) -> None:
        page = HTML.read_text(encoding="utf-8")
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        for key in ("locked", "eligible", "after_first_search"):
            snapshot = receipt[key]
            self.assertIn(snapshot["claim_ceiling"], page)
            self.assertIn(snapshot["evidence_stage_name"], page)
        self.assertIn(receipt["event"]["event_id"], page)
        self.assertIn(receipt["event"]["action"], page)
        self.assertFalse(receipt["after_first_search"]["confirmed_external_life"])

    def test_readiness_projection_keeps_all_six_canonical_checks(self) -> None:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        self.assertEqual(6, len(receipt["locked"]["readiness"]["checks"]))
        self.assertTrue(all(value is False for value in receipt["locked"]["readiness"]["checks"].values()))
        self.assertTrue(all(value is True for value in receipt["eligible"]["readiness"]["checks"].values()))


if __name__ == "__main__":
    unittest.main()
