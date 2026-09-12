from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "temporal_bridge_runtime_smoke_v0_14.cjs"
OUT = ROOT / "output" / "temporal_bridge_candidate" / "runtime_smoke_report_v0_14_0.json"


def main() -> int:
    node = os.environ.get("CODEX_PRIMARY_RUNTIME_NODE", "node")
    result = subprocess.run([node, str(SCRIPT)], cwd=ROOT, text=True, capture_output=True, check=False)
    if result.stdout.strip():
        try:
            report = json.loads(result.stdout)
        except json.JSONDecodeError:
            report = {
                "schema": "axm.temporal-evidence-bridge-runtime-smoke.v1",
                "version": "0.14.0",
                "status": "failed",
                "parse_error": result.stdout,
                "stderr": result.stderr,
            }
    else:
        report = {
            "schema": "axm.temporal-evidence-bridge-runtime-smoke.v1",
            "version": "0.14.0",
            "status": "failed",
            "stderr": result.stderr,
        }
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if result.returncode == 0 and report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
