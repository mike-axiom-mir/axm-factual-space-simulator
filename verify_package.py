from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(root: Path, manifest_path: Path, *, output_snapshot: bool) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = set(manifest["files"])
    if output_snapshot:
        base = root / "output"
        excluded = {"output/OUTPUT_SNAPSHOT_MANIFEST.json", "output/OUTPUT_CHECKSUMS.sha256"}
        actual = {
            p.relative_to(root).as_posix()
            for p in base.rglob("*") if p.is_file()
            and p.relative_to(root).as_posix() not in excluded
            and "__pycache__" not in p.parts and p.suffix != ".pyc"
        }
    else:
        excluded = {
            "PACKAGE_MANIFEST.json", "CHECKSUMS.sha256",
            "output/OUTPUT_SNAPSHOT_MANIFEST.json", "output/OUTPUT_CHECKSUMS.sha256",
        }
        actual = {
            p.relative_to(root).as_posix()
            for p in root.rglob("*") if p.is_file()
            and not p.relative_to(root).as_posix().startswith("output/")
            and ".git" not in p.relative_to(root).parts
            and p.relative_to(root).as_posix() not in excluded
            and "__pycache__" not in p.parts and p.suffix != ".pyc"
        }
    failures = []
    for rel in sorted(expected - actual): failures.append({"file": rel, "error": "missing"})
    for rel in sorted(actual - expected): failures.append({"file": rel, "error": "unexpected_unmanaged_file"})
    for rel in sorted(expected & actual):
        path = root / rel; info = manifest["files"][rel]
        actual_hash = sha256(path)
        if path.stat().st_size != info["bytes"] or actual_hash != info["sha256"]:
            failures.append({
                "file": rel, "error": "mismatch",
                "expected_bytes": info["bytes"], "actual_bytes": path.stat().st_size,
                "expected_sha256": info["sha256"], "actual_sha256": actual_hash,
            })
    return {"checked_files": len(expected), "valid": not failures, "failures": failures}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-only", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    canonical_manifest = json.loads((root / "PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    canonical = verify_manifest(root, root / "PACKAGE_MANIFEST.json", output_snapshot=False)
    output = {"checked_files": 0, "valid": True, "failures": [], "skipped": True}
    if not args.canonical_only:
        output_path = root / "output" / "OUTPUT_SNAPSHOT_MANIFEST.json"
        if output_path.exists():
            output = verify_manifest(root, output_path, output_snapshot=True)
            output["skipped"] = False
        else:
            output = {"checked_files": 0, "valid": False, "failures": [{"error": "missing output snapshot manifest"}], "skipped": False}
    result = {
        "package": canonical_manifest["package"],
        "version": canonical_manifest["version"],
        "canonical": canonical,
        "generated_output_snapshot": output,
        "strict_unmanaged_file_check": True,
        "valid": canonical["valid"] and output["valid"],
    }
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
