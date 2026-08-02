from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
env = os.environ.copy()
env["PYTHONPATH"] = str(ROOT / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
env["PYTHONDONTWRITEBYTECODE"] = "1"

scripts = [
    "build_demo_v0_7.py", "build_demo_v0_8.py", "build_demo_v0_9.py",
    "build_demo_v0_10.py", "build_demo_v0_11.py", "build_demo_v0_12.py",
    "build_demo_v0_13.py", "build_demo_v0_14.py",
    "build_local_handoff_outputs_v0_15.py",
    "refresh_output_snapshot_v0_15.py",
]
for name in scripts:
    cp = subprocess.run([sys.executable, str(ROOT / "scripts" / name)], cwd=ROOT, env=env)
    if cp.returncode:
        raise SystemExit(cp.returncode)

handoff = json.loads((ROOT / "data" / "local_handoff_manifest.json").read_text(encoding="utf-8"))
missing = [rel for rel in handoff["demo_entrypoints"] if not (ROOT / rel).exists()]
if missing:
    raise SystemExit("Demo rebuild completed but promised entrypoints are missing: " + ", ".join(missing))

print("All current demonstration layers rebuilt and every promised demo entrypoint exists.")
print("Open OPEN_LOCAL_HANDOFF.html")
