from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from build_platform_backfeed import CAPSULE_NAME, DIST, canonical_json, check_dist, sha256_file


def _plan_digest(plan_without_digest: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(plan_without_digest).encode("utf-8")).hexdigest()


def build_plan(workshop: Path) -> dict[str, Any]:
    workshop = workshop.resolve()
    if not workshop.is_dir():
        raise ValueError(f"Workshop root does not exist: {workshop}")
    if not (workshop / "tools").is_dir() or not (workshop / "hub").is_dir():
        raise ValueError(f"target is not an AXM Workshop root: {workshop}")
    capsule_check = check_dist()
    if not capsule_check["valid"]:
        raise ValueError(f"backfeed dist is not current: {capsule_check}")
    capsule_path = DIST / CAPSULE_NAME
    capsule = json.loads(capsule_path.read_text(encoding="utf-8"))
    targets = []
    for module in capsule["modules"]:
        target = workshop / "tools" / module["id"]
        targets.append({
            "module_id": module["id"],
            "source": str((DIST / module["root"]).resolve()),
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


def apply_plan(workshop: Path, supplied_digest: str) -> dict[str, Any]:
    plan = build_plan(workshop)
    if supplied_digest != plan["plan_digest"]:
        raise ValueError(f"plan digest mismatch; current plan is {plan['plan_digest']}")
    existing = [row["target"] for row in plan["targets"] if row["target_exists"]]
    if existing:
        raise FileExistsError("refusing to overwrite existing module targets: " + ", ".join(existing))
    capsule = json.loads((DIST / CAPSULE_NAME).read_text(encoding="utf-8"))
    installed = []
    for module in capsule["modules"]:
        source = DIST / module["root"]
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
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--plan-digest")
    args = parser.parse_args(argv)
    if args.apply and not args.plan_digest:
        parser.error("--apply requires --plan-digest")
    try:
        result = apply_plan(args.workshop, args.plan_digest) if args.apply else build_plan(args.workshop)
    except Exception as error:
        print(json.dumps({"valid": False, "error": str(error)}, indent=2, ensure_ascii=False))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
