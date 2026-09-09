from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "platform_backfeed" / "dist"
CAPSULE_NAME = "AXM_BRANCH_CAPSULE.json"
CAPSULE_SCHEMA = "axm.branch-backfeed-capsule/v1"


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


def _reject_symlink_path(root: Path, relative: str) -> None:
    cursor = root
    for part in relative.split("/"):
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"capsule may not contain symbolic links: {relative}")


def verify_capsule(capsule_root: Path) -> dict[str, Any]:
    """Verify a received capsule using only its manifest and payload bytes."""
    capsule_root = capsule_root.resolve()
    if not capsule_root.is_dir():
        raise ValueError(f"capsule root does not exist: {capsule_root}")
    capsule_path = capsule_root / CAPSULE_NAME
    if not capsule_path.is_file() or capsule_path.is_symlink():
        raise ValueError(f"capsule manifest is missing or unsafe: {capsule_path}")
    try:
        capsule = json.loads(capsule_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"capsule manifest is not valid UTF-8 JSON: {error}") from error
    if not isinstance(capsule, dict) or capsule.get("schema") != CAPSULE_SCHEMA:
        raise ValueError("unsupported capsule schema")
    modules = capsule.get("modules")
    inventory = capsule.get("files")
    if not isinstance(modules, list) or not isinstance(inventory, dict):
        raise ValueError("capsule modules and files inventory are required")

    expected: dict[str, dict[str, Any]] = {}
    for raw_path, raw_info in inventory.items():
        relative = _portable_relative(str(raw_path))
        if relative != raw_path or not relative.startswith("modules/"):
            raise ValueError(f"inventory path is outside modules/: {raw_path!r}")
        if not isinstance(raw_info, dict):
            raise ValueError(f"invalid inventory row: {relative}")
        size = raw_info.get("bytes")
        digest = raw_info.get("sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValueError(f"invalid byte count: {relative}")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"invalid SHA-256 digest: {relative}")
        _reject_symlink_path(capsule_root, relative)
        path = capsule_root / relative
        if not path.is_file():
            raise ValueError(f"missing capsule file: {relative}")
        expected[relative] = {"bytes": size, "sha256": digest}

    observed: dict[str, dict[str, Any]] = {}
    for path in capsule_root.rglob("*"):
        relative = path.relative_to(capsule_root).as_posix()
        if path.is_symlink():
            raise ValueError(f"capsule may not contain symbolic links: {relative}")
        if path.is_file() and relative != CAPSULE_NAME:
            observed[relative] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    missing = sorted(set(expected) - set(observed))
    unexpected = sorted(set(observed) - set(expected))
    changed = sorted(path for path in set(expected) & set(observed) if expected[path] != observed[path])
    if missing or unexpected or changed:
        raise ValueError(
            "capsule payload does not match manifest: "
            f"missing={missing}, unexpected={unexpected}, changed={changed}"
        )

    seen_ids: set[str] = set()
    for module in modules:
        if not isinstance(module, dict):
            raise ValueError("invalid module declaration")
        module_id = module.get("id")
        if not isinstance(module_id, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", module_id):
            raise ValueError(f"invalid module id: {module_id!r}")
        if module_id in seen_ids:
            raise ValueError(f"duplicate module id: {module_id}")
        seen_ids.add(module_id)
        root = f"modules/{module_id}"
        if module.get("root") != root or module.get("external_dependencies") != []:
            raise ValueError(f"unsafe module boundary: {module_id}")
        file_paths = module.get("file_paths")
        if not isinstance(file_paths, list) or any(not isinstance(path, str) for path in file_paths):
            raise ValueError(f"invalid module file list: {module_id}")
        declared = [_portable_relative(path) for path in file_paths]
        owned = sorted(path for path in expected if path.startswith(root + "/"))
        if len(declared) != len(set(declared)) or sorted(declared) != owned:
            raise ValueError(f"module file list does not match inventory: {module_id}")
        for field in ("manifest", "contract", "entry"):
            declared_path = _portable_relative(str(module.get(field, "")))
            if not declared_path.startswith(root + "/") or declared_path not in expected:
                raise ValueError(f"module {field} is outside its verified files: {module_id}")

    return {
        "schema": "axm.branch-backfeed-capsule-verification/v1",
        "valid": True,
        "capsule_id": capsule.get("capsule_id"),
        "capsule_manifest_sha256": sha256_file(capsule_path),
        "module_count": len(modules),
        "file_count": len(expected),
    }


def _plan_digest(plan_without_digest: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(plan_without_digest).encode("utf-8")).hexdigest()


def build_plan(workshop: Path, capsule_root: Path = DIST) -> dict[str, Any]:
    workshop = workshop.resolve()
    capsule_root = capsule_root.resolve()
    if not workshop.is_dir():
        raise ValueError(f"Workshop root does not exist: {workshop}")
    if not (workshop / "tools").is_dir() or not (workshop / "hub").is_dir():
        raise ValueError(f"target is not an AXM Workshop root: {workshop}")
    capsule_check = verify_capsule(capsule_root)
    capsule_path = capsule_root / CAPSULE_NAME
    capsule = json.loads(capsule_path.read_text(encoding="utf-8"))
    targets = []
    for module in capsule["modules"]:
        target = workshop / "tools" / module["id"]
        targets.append({
            "module_id": module["id"],
            "source": str((capsule_root / module["root"]).resolve()),
            "target": str(target),
            "target_exists": target.exists(),
        })
    seams = {}
    for relative in ("hub/module-contract-verifier.js", "hub/graft-core.js"):
        path = workshop / relative
        seams[relative] = sha256_file(path) if path.is_file() else None
    plan = {
        "schema": "axm.branch-backfeed-install-plan/v1",
        "workshop": str(workshop),
        "capsule_id": capsule["capsule_id"],
        "capsule_manifest_sha256": sha256_file(capsule_path),
        "targets": targets,
        "shared_seams_read_only": seams,
        "mutations": {
            "new_tool_leaf_directories_only": True,
            "registry": False,
            "hub_entrypoint": False,
            "foundation_spine": False,
            "permissions": False,
            "canon": False,
        },
    }
    plan["plan_digest"] = _plan_digest(plan)
    return plan


def _verify_installed_module(target: Path, module: dict[str, Any], capsule: dict[str, Any]) -> list[str]:
    failures = []
    prefix = module["root"] + "/"
    expected = {path[len(prefix):]: info for path, info in capsule["files"].items() if path.startswith(prefix)}
    observed = {
        path.relative_to(target).as_posix(): {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in target.rglob("*") if path.is_file()
    }
    for path in sorted(set(expected) | set(observed)):
        if path not in expected:
            failures.append(f"unexpected installed file: {module['id']}/{path}")
        elif path not in observed:
            failures.append(f"missing installed file: {module['id']}/{path}")
        elif expected[path] != observed[path]:
            failures.append(f"installed hash or byte mismatch: {module['id']}/{path}")
    return failures


def apply_plan(workshop: Path, supplied_digest: str, capsule_root: Path = DIST) -> dict[str, Any]:
    capsule_root = capsule_root.resolve()
    plan = build_plan(workshop, capsule_root)
    if supplied_digest != plan["plan_digest"]:
        raise ValueError(f"plan digest mismatch; current plan is {plan['plan_digest']}")
    existing = [row["target"] for row in plan["targets"] if row["target_exists"]]
    if existing:
        raise FileExistsError("refusing to overwrite existing module targets: " + ", ".join(existing))
    capsule = json.loads((capsule_root / CAPSULE_NAME).read_text(encoding="utf-8"))
    installed = []
    for module in capsule["modules"]:
        source = capsule_root / module["root"]
        target = workshop.resolve() / "tools" / module["id"]
        staging = target.with_name(f".branch-backfeed-staging-{module['id']}-{supplied_digest[:12]}")
        if staging.exists():
            raise FileExistsError(f"stale staging target requires review: {staging}")
        shutil.copytree(source, staging)
        failures = _verify_installed_module(staging, module, capsule)
        if failures:
            shutil.rmtree(staging)
            raise ValueError("; ".join(failures))
        os.replace(staging, target)
        installed.append({"module_id": module["id"], "target": str(target)})
    receipt = {
        "schema": "axm.branch-backfeed-install-receipt/v1",
        "plan_digest": supplied_digest,
        "capsule_id": capsule["capsule_id"],
        "capsule_manifest_sha256": plan["capsule_manifest_sha256"],
        "installed": installed,
        "shared_seams_changed": [],
        "registry_changed": False,
        "promoted": False,
        "next_gate": "Run Workshop contract verification and Graft review before registration.",
    }
    receipt_dir = workshop.resolve() / "state" / "branch-backfeed" / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_dir / f"{supplied_digest}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan or apply a leaf-only AXM Workshop backfeed install.")
    parser.add_argument("--workshop", type=Path, required=True)
    parser.add_argument(
        "--capsule",
        type=Path,
        default=DIST,
        help="received capsule directory (defaults to this checkout's platform_backfeed/dist)",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--plan-digest")
    args = parser.parse_args(argv)
    if args.apply and not args.plan_digest:
        parser.error("--apply requires --plan-digest")
    try:
        result = (
            apply_plan(args.workshop, args.plan_digest, args.capsule)
            if args.apply
            else build_plan(args.workshop, args.capsule)
        )
    except Exception as error:
        print(json.dumps({"valid": False, "error": str(error)}, indent=2, ensure_ascii=False))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
