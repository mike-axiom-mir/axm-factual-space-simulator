from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable


MANIFEST_NAME = "PACKAGE_MANIFEST.json"
CHECKSUMS_NAME = "CHECKSUMS.sha256"
OUTPUT_MANIFEST = "output/OUTPUT_SNAPSHOT_MANIFEST.json"
OUTPUT_CHECKSUMS = "output/OUTPUT_CHECKSUMS.sha256"

_EXCLUDED = {
    MANIFEST_NAME,
    CHECKSUMS_NAME,
    OUTPUT_MANIFEST,
    OUTPUT_CHECKSUMS,
    f".{MANIFEST_NAME}.tmp",
    f".{CHECKSUMS_NAME}.tmp",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_paths(root: Path) -> Iterable[tuple[str, Path]]:
    root = root.resolve()
    rows: list[tuple[str, Path]] = []
    for current, directory_names, file_names in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        kept_directories: list[str] = []
        for name in sorted(directory_names, key=str.casefold):
            candidate = current_path / name
            relative = candidate.relative_to(root).as_posix()
            if candidate.is_symlink():
                raise ValueError(f"portable package seals do not support symbolic links: {candidate}")
            if relative == "output" or relative == ".git" or name == "__pycache__":
                continue
            kept_directories.append(name)
        directory_names[:] = kept_directories

        for name in sorted(file_names, key=str.casefold):
            path = current_path / name
            if path.is_symlink():
                raise ValueError(f"portable package seals do not support symbolic links: {path}")
            relative = path.relative_to(root).as_posix()
            if relative in _EXCLUDED or path.suffix == ".pyc":
                continue
            rows.append((relative, path))
    yield from sorted(rows, key=lambda row: row[0].casefold())


def build_manifest(root: Path, template: dict[str, Any] | None = None) -> dict[str, Any]:
    root = root.resolve()
    if template is None:
        template = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
    files = {
        relative: {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for relative, path in canonical_paths(root)
    }
    base = {key: value for key, value in template.items() if key not in {"managed_file_count", "files"}}
    return {**base, "managed_file_count": len(files), "files": files}


def checksum_text(manifest: dict[str, Any]) -> str:
    return "".join(
        f"{info['sha256']}  {relative}\n"
        for relative, info in manifest["files"].items()
    )


def check_seal(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = root / MANIFEST_NAME
    checksums_path = root / CHECKSUMS_NAME
    failures: list[dict[str, Any]] = []
    if not manifest_path.exists():
        return {"valid": False, "managed_file_count": 0, "failures": [{"error": "missing package manifest"}]}
    if not checksums_path.exists():
        return {"valid": False, "managed_file_count": 0, "failures": [{"error": "missing checksum list"}]}

    recorded = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = build_manifest(root, recorded)
    if recorded != expected:
        recorded_files = recorded.get("files", {})
        expected_files = expected["files"]
        for relative in sorted(set(recorded_files) | set(expected_files)):
            if relative not in recorded_files:
                failures.append({"file": relative, "error": "missing_from_manifest"})
            elif relative not in expected_files:
                failures.append({"file": relative, "error": "unexpected_in_manifest"})
            elif recorded_files[relative] != expected_files[relative]:
                failures.append({
                    "file": relative,
                    "error": "hash_or_size_mismatch",
                    "recorded": recorded_files[relative],
                    "observed": expected_files[relative],
                })
        if recorded.get("managed_file_count") != expected["managed_file_count"]:
            failures.append({
                "error": "managed_file_count_mismatch",
                "recorded": recorded.get("managed_file_count"),
                "observed": expected["managed_file_count"],
            })

    recorded_checksums = checksums_path.read_text(encoding="utf-8")
    expected_checksums = checksum_text(expected)
    if recorded_checksums != expected_checksums:
        failures.append({"error": "checksum_list_mismatch"})
    return {
        "valid": not failures,
        "managed_file_count": expected["managed_file_count"],
        "failures": failures,
    }


def _atomic_write_text(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def write_seal(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = root / MANIFEST_NAME
    template = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = build_manifest(root, template)
    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    checksums = checksum_text(manifest)
    _atomic_write_text(root / CHECKSUMS_NAME, checksums)
    _atomic_write_text(manifest_path, manifest_text)
    result = check_seal(root)
    result.update({
        "manifest_sha256": sha256_file(manifest_path),
        "checksums_sha256": sha256_file(root / CHECKSUMS_NAME),
    })
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check or deterministically reseal the canonical AXM package manifest."
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check only; this is the default")
    mode.add_argument("--write", action="store_true", help="atomically replace the two canonical seal files")
    args = parser.parse_args(argv)
    result = write_seal(args.root) if args.write else check_seal(args.root)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
