from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
MANIFEST = OUTPUT / "OUTPUT_SNAPSHOT_MANIFEST.json"
CHECKSUMS = OUTPUT / "OUTPUT_CHECKSUMS.sha256"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    files = {}
    for path in sorted(OUTPUT.rglob("*")):
        if not path.is_file() or path in {MANIFEST, CHECKSUMS}:
            continue
        rel = path.relative_to(ROOT).as_posix()
        files[rel] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    payload = {
        "schema": "axm.generated-output-snapshot-manifest.v1",
        "package": "AXM_FACTUAL_STAR_ADVENTURE_SIMULATOR",
        "version": "0.15.0",
        "policy": "Generated outputs may contain truthful creation timestamps. Rebuilds refresh this snapshot; canonical source integrity is tracked separately.",
        "file_count": len(files),
        "files": files,
    }
    MANIFEST.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    CHECKSUMS.write_text(
        "\n".join(f"{info['sha256']}  {rel}" for rel, info in sorted(files.items())) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output_files": len(files), "manifest": MANIFEST.relative_to(ROOT).as_posix()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
