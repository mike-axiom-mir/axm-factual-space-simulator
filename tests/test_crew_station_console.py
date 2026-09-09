from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "assets" / "demo_templates" / "crew_station_console.html"
OUTPUT = ROOT / "output" / "crew_station_metric_demo" / "crew_station_console.html"


class CrewStationConsoleTests(unittest.TestCase):
    def test_console_template_exposes_truthful_attention_controls(self) -> None:
        text = TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("Derived display priority · canonical mode unchanged", text)
        self.assertIn("button.className='filter-button'", text)
        self.assertIn("button.type='button'", text)
        self.assertIn("button.setAttribute('aria-pressed'", text)
        self.assertIn("prefers-reduced-motion:reduce", text)
        self.assertIn("selectMetric(card,button)", text)

    def test_builder_binds_current_report_without_changing_station_truth(self) -> None:
        subprocess.run([sys.executable, "scripts/build_demo_v0_14.py"], cwd=ROOT, check=True)
        output = OUTPUT.read_text(encoding="utf-8")

        self.assertNotIn("__CREW_STATION_DATA__", output)
        marker = '<script type="application/json" id="data">'
        start = output.index(marker) + len(marker)
        end = output.index("</script>", start)
        embedded = json.loads(output[start:end])
        report = json.loads((ROOT / "output" / "crew_station_metric_demo" / "demo_report.json").read_text(encoding="utf-8"))

        self.assertEqual(embedded["stations"], report["station_views"]["views"])
        self.assertEqual(embedded["learning"], report["learning_pressure"])
        self.assertEqual(embedded["stations"]["command_duet"]["mode"], report["current_ship_state"]["mode"])
