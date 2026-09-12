import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "assets" / "demo_templates" / "ship_blueprint_console.html"
OUTPUT = ROOT / "output" / "factual_ship_blueprint_demo" / "ship_blueprint_console.html"

class ShipBlueprintConsoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = TEMPLATE.read_text(encoding="utf-8")

    def test_generated_console_matches_source_template(self):
        self.assertEqual(self.source, OUTPUT.read_text(encoding="utf-8"))

    def test_modules_are_keyboard_operable_and_stateful(self):
        self.assertEqual(self.source.count('type="button" class="module'), 5)
        self.assertIn('"ArrowRight","ArrowDown","ArrowLeft","ArrowUp","Home","End"', self.source)
        self.assertIn('modules[next].focus();selectModule(modules[next])', self.source)

    def test_phone_realization_reflows_instead_of_cropping_ship(self):
        self.assertIn("@media(max-width:700px)", self.source)
        self.assertIn(".ship{display:grid;gap:8px;aspect-ratio:auto;clip-path:none", self.source)
        self.assertIn(".module{position:static;width:auto;height:auto", self.source)

    def test_state_status_does_not_collide_with_window_status(self):
        self.assertIn('id="stateStatus"', self.source)
        self.assertIn('const stateStatus=byId("stateStatus")', self.source)
        self.assertNotIn('id="status"', self.source)

    def test_role_view_is_readable_and_authority_bounded(self):
        self.assertIn("Derived starting perspective · simulation metrics, not qualification", self.source)
        self.assertIn("panel.replaceChildren()", self.source)
        self.assertNotIn("JSON.stringify", self.source)
        self.assertIn('aria-live="polite"', self.source)

    def test_unavailable_report_admits_no_telemetry(self):
        self.assertIn("No telemetry was admitted.", self.source)
        self.assertIn('stateStatus.textContent="demo state unavailable"', self.source)

if __name__ == "__main__":
    unittest.main()
