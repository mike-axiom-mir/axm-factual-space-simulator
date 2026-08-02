from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKFEED = ROOT / "platform_backfeed"
RECIPE_PATH = BACKFEED / "backfeed.recipe.json"
DIST = BACKFEED / "dist"
CAPSULE_NAME = "AXM_BRANCH_CAPSULE.json"
CAPSULE_SCHEMA = "axm.branch-backfeed-capsule/v1"
BUILTIN_REQUIRES = {"assert", "crypto"}
LIFECYCLE_VALUES = {
    "state_owner": {"browser", "service", "filesystem", "mixed", "none"},
    "reload": {"resume", "reset", "not-applicable", "pending"},
    "disconnect": {"reconnect", "graceful-degrade", "not-applicable", "pending"},
    "cleanup": {"automatic", "explicit", "not-applicable", "pending"},
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _portable_relative(path: str) -> str:
    if not path or "\\" in path or path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        raise ValueError(f"not a portable relative path: {path!r}")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"path contains an empty, dot, or parent segment: {path!r}")
    return "/".join(parts)


def _module_files(module_root: Path) -> list[Path]:
    rows = []
    for path in module_root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"backfeed modules may not contain symbolic links: {path}")
        if path.is_file():
            rows.append(path)
    return sorted(rows, key=lambda path: path.relative_to(module_root).as_posix().casefold())


def _check_no_external_dependencies(module_id: str, files: list[Path]) -> None:
    failures: list[str] = []
    require_pattern = re.compile(r"require\(\s*['\"]([^'\"]+)['\"]\s*\)")
    import_pattern = re.compile(r"(?:from\s+|import\s*\(\s*)['\"]([^'\"]+)['\"]")
    remote_pattern = re.compile(r"(?:src|href)\s*=\s*['\"](?:https?:)?//", re.IGNORECASE)
    for path in files:
        if path.suffix.lower() not in {".js", ".mjs", ".html"}:
            continue
        text = path.read_text(encoding="utf-8")
        for name in require_pattern.findall(text) + import_pattern.findall(text):
            if name.startswith("./") or name.startswith("../") or name.startswith("node:") or name in BUILTIN_REQUIRES:
                continue
            failures.append(f"{path.name}: external module reference {name!r}")
        if path.suffix.lower() == ".html" and remote_pattern.search(text):
            failures.append(f"{path.name}: remote script or stylesheet reference")
    if failures:
        raise ValueError(f"{module_id} is not dependency-free: " + "; ".join(failures))


def _validate_module_contract(module_id: str, manifest: dict[str, Any], contract: dict[str, Any], source_root: Path) -> None:
    failures: list[str] = []
    for field in ("uses", "permissions"):
        if not isinstance(manifest.get(field), list):
            failures.append(f"manifest.{field} must be an array")
    for field in ("provides", "consumes", "permissions"):
        if not isinstance(contract.get(field), list):
            failures.append(f"contract.{field} must be an array")
    if manifest.get("permissions") != contract.get("permissions"):
        failures.append("manifest and contract permissions differ")
    if manifest.get("contract") != "module.contract.json":
        failures.append("manifest must declare module.contract.json")
    for field in ("entry", "contract"):
        try:
            relative = _portable_relative(str(manifest.get(field, "")))
        except ValueError as error:
            failures.append(str(error))
            continue
        if not (source_root / relative).is_file():
            failures.append(f"declared {field} is missing: {relative}")
    handoffs = contract.get("handoffs")
    if not isinstance(handoffs, dict) or not isinstance(handoffs.get("emits"), list) or not isinstance(handoffs.get("accepts"), list):
        failures.append("contract.handoffs must contain emits and accepts arrays")
    boundaries = contract.get("boundaries")
    if not isinstance(boundaries, dict) or not isinstance(boundaries.get("refuses"), list):
        failures.append("contract.boundaries.refuses must be an array")
    lifecycle = contract.get("lifecycle")
    if not isinstance(lifecycle, dict):
        failures.append("contract.lifecycle is required")
    else:
        for field, allowed in LIFECYCLE_VALUES.items():
            if lifecycle.get(field) not in allowed:
                failures.append(f"unsupported lifecycle.{field}")
    if failures:
        raise ValueError(f"invalid Workshop module contract for {module_id}: " + "; ".join(failures))


def build_capsule(output_dir: Path) -> dict[str, Any]:
    recipe = json.loads(RECIPE_PATH.read_text(encoding="utf-8"))
    if recipe.get("schema") != "axm.branch-backfeed-recipe/v1":
        raise ValueError("unsupported backfeed recipe schema")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    modules_out = output_dir / "modules"
    modules_out.mkdir(parents=True, exist_ok=True)
    capsule_modules: list[dict[str, Any]] = []
    inventory: dict[str, dict[str, Any]] = {}
    seen_ids: set[str] = set()

    for declaration in recipe.get("modules", []):
        module_id = str(declaration.get("id", ""))
        if not module_id or module_id in seen_ids:
            raise ValueError(f"missing or duplicate module id: {module_id!r}")
        seen_ids.add(module_id)
        if declaration.get("external_dependencies") != []:
            raise ValueError(f"external dependencies are not allowed: {module_id}")
        source_relative = _portable_relative(str(declaration.get("root", "")))
        source_root = (BACKFEED / source_relative).resolve()
        if not source_root.is_relative_to((BACKFEED / "source" / "modules").resolve()):
            raise ValueError(f"module source escapes reviewed source root: {module_id}")
        files = _module_files(source_root)
        if not files:
            raise ValueError(f"module has no files: {module_id}")
        manifest = json.loads((source_root / "manifest.json").read_text(encoding="utf-8"))
        contract = json.loads((source_root / "module.contract.json").read_text(encoding="utf-8"))
        if manifest.get("schema") != "axm.tool-manifest/v1" or manifest.get("id") != module_id:
            raise ValueError(f"manifest identity mismatch: {module_id}")
        if contract.get("schema") != "axm.module-contract/v1" or contract.get("id") != module_id:
            raise ValueError(f"contract identity mismatch: {module_id}")
        if manifest.get("status") != recipe["policy"]["target_status"]:
            raise ValueError(f"module must enter as {recipe['policy']['target_status']}: {module_id}")
        if manifest.get("permissions") != [] or contract.get("permissions") != []:
            raise ValueError(f"backfeed bootstrap may not request permissions: {module_id}")
        _validate_module_contract(module_id, manifest, contract, source_root)
        _check_no_external_dependencies(module_id, files)

        target_root = modules_out / module_id
        target_root.mkdir(parents=True, exist_ok=True)
        file_paths: list[str] = []
        for source in files:
            relative_inside = source.relative_to(source_root).as_posix()
            destination = target_root / relative_inside
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            capsule_relative = destination.relative_to(output_dir).as_posix()
            file_paths.append(capsule_relative)
            inventory[capsule_relative] = {
                "bytes": destination.stat().st_size,
                "sha256": sha256_file(destination),
            }
        root_relative = f"modules/{module_id}"
        capsule_modules.append({
            "id": module_id,
            "version": manifest.get("version"),
            "root": root_relative,
            "manifest": f"{root_relative}/manifest.json",
            "contract": f"{root_relative}/module.contract.json",
            "entry": f"{root_relative}/{_portable_relative(str(manifest.get('entry', '')))}",
            "file_paths": file_paths,
            "external_dependencies": [],
            "runtime_primitives": ["ECMAScript", "browser APIs when declared by the module"],
            "origin": list(declaration.get("origin", [])),
        })

    capsule = {
        "schema": CAPSULE_SCHEMA,
        "capsule_id": recipe["capsule_id"],
        "source": recipe["source"],
        "policy": recipe["policy"],
        "modules": capsule_modules,
        "files": dict(sorted(inventory.items(), key=lambda item: item[0].casefold())),
        "claim_boundary": (
            "Hashes prove selected-byte identity only. Graft, behavior tests, visual checks, authority, "
            "registration, and promotion remain separate gates."
        ),
    }
    (output_dir / CAPSULE_NAME).write_text(
        json.dumps(capsule, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    return capsule


def tree_inventory(root: Path) -> dict[str, dict[str, Any]]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold())
        if path.is_file()
    }


def check_dist() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="axm-backfeed-check-") as temporary:
        expected_root = Path(temporary) / "dist"
        capsule = build_capsule(expected_root)
        expected = tree_inventory(expected_root)
    observed = tree_inventory(DIST)
    missing = sorted(set(expected) - set(observed))
    unexpected = sorted(set(observed) - set(expected))
    changed = sorted(path for path in set(expected) & set(observed) if expected[path] != observed[path])
    return {
        "schema": "axm.branch-backfeed-build-check/v1",
        "valid": not (missing or unexpected or changed),
        "capsule_id": capsule["capsule_id"],
        "module_count": len(capsule["modules"]),
        "file_count": len(capsule["files"]),
        "missing": missing,
        "unexpected": unexpected,
        "changed": changed,
    }


def write_dist() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="axm-backfeed-write-") as temporary:
        staged = Path(temporary) / "dist"
        capsule = build_capsule(staged)
        resolved_dist = DIST.resolve()
        if resolved_dist != (BACKFEED / "dist").resolve():
            raise RuntimeError("refusing to replace an unexpected output directory")
        if DIST.exists():
            shutil.rmtree(DIST)
        shutil.copytree(staged, DIST)
    check = check_dist()
    check.update({
        "written": True,
        "capsule_manifest_sha256": sha256_file(DIST / CAPSULE_NAME),
        "capsule_json_sha256": hashlib.sha256(canonical_json(capsule).encode("utf-8")).hexdigest(),
    })
    return check


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or verify the dependency-free AXM branch backfeed capsule.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="replace the generated dist directory")
    mode.add_argument("--check", action="store_true", help="verify dist; this is the default")
    args = parser.parse_args(argv)
    result = write_dist() if args.write else check_dist()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
