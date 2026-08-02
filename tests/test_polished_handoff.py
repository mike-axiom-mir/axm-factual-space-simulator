from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class _LocalDoorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.images: list[str] = []
        self.lang = ""
        self.has_viewport = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "html":
            self.lang = values.get("lang") or ""
        elif tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
        elif tag == "img" and values.get("src"):
            self.images.append(values["src"] or "")
        elif tag == "meta" and values.get("name") == "viewport":
            self.has_viewport = bool(values.get("content"))


class PolishedLocalHandoffTests(unittest.TestCase):
    subsystem_links = {
        "output/crew_station_metric_demo/crew_station_console.html",
        "output/factual_ship_blueprint_demo/ship_blueprint_console.html",
        "output/ship_interior_demo/ship_interior_console.html",
        "output/rooted_crew_demo/rooted_crew_console.html",
        "output/bridge_visual_core_demo/paint_foundation_bridge.html",
        "output/adventure_slot_demo/slot_manager.html",
        "output/persistent_atlas_demo/atlas.html",
        "output/contact_horizon_demo/contact_horizon_console.html",
    }

    def test_local_door_is_offline_complete_and_links_exist(self) -> None:
        source = (ROOT / "OPEN_LOCAL_HANDOFF.html").read_text(encoding="utf-8")
        parser = _LocalDoorParser()
        parser.feed(source)

        self.assertEqual(parser.lang, "en")
        self.assertTrue(parser.has_viewport)
        self.assertIn("Concept art — not simulation telemetry.", source)
        self.assertEqual({link for link in parser.links if link in self.subsystem_links}, self.subsystem_links)
        for link in self.subsystem_links:
            self.assertGreaterEqual(parser.links.count(link), 1)

        local_targets = [target for target in parser.links + parser.images if not target.startswith("#")]
        self.assertTrue(local_targets)
        for target in local_targets:
            self.assertFalse(re.match(r"^(?:https?:)?//", target, flags=re.IGNORECASE), target)
            self.assertTrue((ROOT / target).is_file(), target)

    def test_root_launchers_are_location_independent_and_utf8_explicit(self) -> None:
        batch_files = sorted(ROOT.glob("run_*.bat"))
        shell_files = sorted(ROOT.glob("run_*.sh"))
        self.assertTrue(batch_files)
        self.assertTrue(shell_files)

        for path in batch_files:
            source = path.read_text(encoding="utf-8")
            self.assertIn("setlocal", source, path.name)
            self.assertIn('cd /d "%~dp0"', source, path.name)
            self.assertIn('set "PYTHONUTF8=1"', source, path.name)
            self.assertIn('set "PYTHONIOENCODING=utf-8"', source, path.name)

        for path in shell_files:
            source = path.read_text(encoding="utf-8")
            self.assertIn("set -eu", source, path.name)
            self.assertIn('$(dirname -- "$0")', source, path.name)
            self.assertIn("export PYTHONUTF8=1", source, path.name)
            self.assertIn("export PYTHONIOENCODING=utf-8", source, path.name)


if __name__ == "__main__":
    unittest.main()
