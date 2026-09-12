from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "output" / "temporal_bridge_candidate" / "temporal_bridge.html"
OUT = ROOT / "output" / "temporal_bridge_candidate" / "browser_smoke_report.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    executable = os.environ.get("AXM_CHROMIUM_EXECUTABLE")
    if not executable:
        report = {
            "schema": "axm.temporal-bridge-browser-smoke.v1",
            "version": "0.14.0",
            "status": "MISSING_VISUAL_CAPTURE",
            "reason": "AXM_CHROMIUM_EXECUTABLE is not set",
            "verdict": "UNKNOWN",
        }
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        report = {
            "schema": "axm.temporal-bridge-browser-smoke.v1",
            "version": "0.14.0",
            "status": "MISSING_VISUAL_CAPTURE",
            "reason": f"Playwright unavailable: {exc}",
            "verdict": "UNKNOWN",
        }
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    checks: list[dict] = []
    temporary_paths: list[Path] = []
    started = time.time()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=executable, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        page.goto(TARGET.as_uri())
        page.wait_for_function("window.__axmMainBridge && window.__axmMainBridgeControl")
        initial = page.evaluate("window.__axmMainBridge")
        baseline = Path(tempfile.mkstemp(prefix="axm-v014-baseline-", suffix=".png")[1])
        active = Path(tempfile.mkstemp(prefix="axm-v014-active-", suffix=".png")[1])
        target = Path(tempfile.mkstemp(prefix="axm-v014-target-", suffix=".png")[1])
        mobile = Path(tempfile.mkstemp(prefix="axm-v014-mobile-", suffix=".png")[1])
        temporary_paths.extend([baseline, active, target, mobile])
        page.screenshot(path=str(baseline), full_page=False)
        source_clock = page.locator("#missionClockLabel").inner_text()
        display_clock = page.locator("#displayClockLabel").inner_text()
        page.click("#playToggle")
        page.wait_for_timeout(500)
        moving = page.evaluate("window.__axmMainBridge")
        page.screenshot(path=str(active), full_page=False)
        page.click("#playToggle")
        paused = page.evaluate("window.__axmMainBridge")
        page.wait_for_timeout(250)
        paused_later = page.evaluate("window.__axmMainBridge")
        page.select_option("#cameraSelect", "target_focus")
        page.select_option("#labelSelect", "all")
        framed = page.evaluate("window.__axmMainBridge")
        inspect_value = page.locator("#inspectSelect option").nth(2).get_attribute("value")
        page.select_option("#inspectSelect", inspect_value)
        inspected = page.evaluate("window.__axmMainBridge")
        page.locator("#replayScrubber").fill("16.5")
        scrubbed = page.evaluate("window.__axmMainBridge")
        page.screenshot(path=str(target), full_page=False)
        page.check("#reducedMotion")
        page.click("#playToggle")
        reduced = page.evaluate("window.__axmMainBridge")
        page.select_option("#cueSelect", "3")
        cue = page.evaluate("window.__axmMainBridge")
        checks.extend([
            {"name": "initially paused", "pass": initial["playing"] is False},
            {"name": "continuous frames advance", "pass": moving["frameCount"] > initial["frameCount"]},
            {"name": "display phase advances", "pass": moving["displaySeconds"] > initial["displaySeconds"]},
            {"name": "visible canvas changes", "pass": digest(baseline) != digest(active)},
            {"name": "pause freezes frame count", "pass": paused_later["frameCount"] == paused["frameCount"]},
            {"name": "source and display clocks are visibly distinct", "pass": source_clock == "T+03:00" and display_clock == "00:00.0"},
            {"name": "target camera is presentation state", "pass": framed["cameraPreset"] == "target_focus" and framed["authority"] == "presentation_state_only"},
            {"name": "label density is presentation state", "pass": framed["labelMode"] == "all"},
            {"name": "object inspector is presentation state", "pass": inspected["inspectedPlanetId"] == inspect_value and inspected["mayRetargetEvent"] is False},
            {"name": "replay scrubber reaches third receipt", "pass": scrubbed["cueIndex"] == 2 and scrubbed["scrubberSeconds"] == 16.5},
            {"name": "scrubber cannot modify runtime resources", "pass": scrubbed["mayModifyRuntimeResources"] is False},
            {"name": "state-change receipt exposed", "pass": scrubbed["stateChangeReceiptStatus"] == "STATE_CHANGES_VALID" and scrubbed["eventDeltaCount"] > 0},
            {"name": "camera framing changes visible canvas", "pass": digest(baseline) != digest(target)},
            {"name": "reduced motion blocks restart", "pass": reduced["playing"] is False},
            {"name": "manual receipt focus", "pass": cue["cueIndex"] == 3},
            {"name": "ledger head ends at source mission time", "pass": cue["cueMissionEndHours"] == cue["missionTimeHours"]},
            {"name": "wall-clock age remains unknown", "pass": cue["wallClockAgeStatus"] == "UNKNOWN_NO_TIMESTAMP"},
            {"name": "authority remains presentation only", "pass": cue["authority"] == "presentation_state_only"},
        ])
        page.set_viewport_size({"width": 390, "height": 844})
        page.reload()
        page.wait_for_function("window.__axmMainBridge")
        page.screenshot(path=str(mobile), full_page=False)
        box = page.locator("#bridgeCanvas").bounding_box()
        checks.extend([
            {"name": "mobile canvas exists", "pass": bool(box and box["width"] > 300 and box["height"] > 400)},
            {"name": "mobile body has no horizontal overflow", "pass": page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")},
        ])
        browser.close()

    failed = [row for row in checks if not row["pass"]]
    report = {
        "schema": "axm.temporal-bridge-browser-smoke.v1",
        "version": "0.14.0",
        "status": "passed" if not failed else "failed",
        "verdict": "PASS" if not failed else "FAIL",
        "checks_passed": len(checks) - len(failed),
        "checks_total": len(checks),
        "checks": checks,
        "failures": failed,
        "capture_duration_seconds": round(time.time() - started, 3),
        "buffer_digest": {
            "baseline_sha256": digest(temporary_paths[0]),
            "active_sha256": digest(temporary_paths[1]),
            "target_focus_sha256": digest(temporary_paths[2]),
            "mobile_sha256": digest(temporary_paths[3]),
        },
        "raw_frames_retained": False,
    }
    for path in temporary_paths:
        path.unlink(missing_ok=True)
    report["temporary_paths_deleted"] = all(not path.exists() for path in temporary_paths)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
