from __future__ import annotations

import ast
import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
TEXT_EXTENSIONS = {".py", ".md", ".txt", ".json", ".toml", ".sh", ".bat", ".html", ".mjs"}


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _check(checks: list[dict[str, Any]], name: str, valid: bool, details: Any = None) -> None:
    checks.append({"name": name, "valid": bool(valid), "details": details})


def audit_package(root: Path | None = None, *, full: bool = False, check_manifest: bool = True) -> dict[str, Any]:
    root = Path(root or PACKAGE_ROOT).resolve()
    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    try:
        pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        version = pyproject["project"]["version"]
        init_text = (root / "src/axm_star_sim/__init__.py").read_text(encoding="utf-8")
        init_match = re.search(r'__version__\s*=\s*["\']([^"\']+)', init_text)
        init_version = init_match.group(1) if init_match else None
        manifest_version = json.loads((root / "data/local_handoff_manifest.json").read_text(encoding="utf-8"))["version"]
        valid = version == init_version == manifest_version
        _check(checks, "version consistency", valid, {"pyproject": version, "package": init_version, "handoff": manifest_version})
        if not valid: failures.append("version consistency")
    except Exception as exc:
        _check(checks, "version consistency", False, str(exc)); failures.append("version consistency")
        version = "unknown"

    json_errors = []
    for path in sorted(root.rglob("*.json")):
        try: json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc: json_errors.append({"file": path.relative_to(root).as_posix(), "error": str(exc)})
    _check(checks, "all JSON parses", not json_errors, json_errors)
    if json_errors: failures.append("JSON parsing")

    syntax_errors = []
    for path in sorted(list((root/"src").rglob("*.py")) + list((root/"scripts").rglob("*.py")) + list((root/"tests").rglob("*.py"))):
        try: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception as exc: syntax_errors.append({"file": path.relative_to(root).as_posix(), "error": str(exc)})
    _check(checks, "Python syntax", not syntax_errors, syntax_errors)
    if syntax_errors: failures.append("Python syntax")

    handoff = json.loads((root/"data/local_handoff_manifest.json").read_text(encoding="utf-8"))
    required = [handoff["canonical_open_file"], handoff["start_here"], handoff["human_handoff"], handoff["machine_handoff"]]
    required += handoff["canonical_registries"] + handoff["demo_entrypoints"] + handoff["required_docs"]
    missing = sorted({path for path in required if not (root/path).exists()})
    _check(checks, "handoff paths exist", not missing, missing)
    if missing: failures.append("handoff paths")

    broken_refs = []
    pattern = re.compile(r'((?:output|docs|data|scripts|src|tests)/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)')
    for name in ("README.md", "START_HERE.txt", "LOCAL_INTAKE_HANDOFF.txt", "docs/LOCAL_HANDOFF_MASTER_v0_15_0.md"):
        text = (root/name).read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            rel = match.group(1).rstrip(".,;:)")
            if not (root/rel).exists(): broken_refs.append({"document": name, "path": rel})
    _check(checks, "key document references", not broken_refs, broken_refs)
    if broken_refs: failures.append("broken key references")

    absolute_paths = []
    absolute_needle = "/mnt" + "/data/"
    scan_roots = [root / name for name in ("README.md", "START_HERE.txt", "LOCAL_INTAKE_HANDOFF.txt", "MACHINE_INTAKE.json")]
    scan_roots += [root / name for name in ("src", "scripts", "data", "docs", "output")]
    candidates = []
    for scan_root in scan_roots:
        if scan_root.is_file(): candidates.append(scan_root)
        elif scan_root.exists(): candidates.extend(path for path in scan_root.rglob("*") if path.is_file())
    for path in candidates:
        if path.suffix.lower() not in TEXT_EXTENSIONS: continue
        try: text = path.read_text(encoding="utf-8")
        except Exception: continue
        if absolute_needle in text:
            absolute_paths.append(path.relative_to(root).as_posix())
    _check(checks, "no container absolute paths", not absolute_paths, absolute_paths)
    if absolute_paths: failures.append("container paths")

    # Runtime tests can legitimately create local __pycache__ files after extraction.
    # Package cleanliness is defined by the signed/hashed manifest, not transient runtime files.
    packaged_bytecode: list[str] = []
    transient_bytecode = [
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.name == "__pycache__" or p.suffix == ".pyc"
    ]
    if check_manifest:
        try:
            package_manifest = json.loads((root / "PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
            packaged_bytecode = sorted(
                rel for rel in package_manifest.get("files", {})
                if "__pycache__" in Path(rel).parts or Path(rel).suffix == ".pyc"
            )
        except Exception as exc:
            packaged_bytecode = [f"manifest_read_error:{exc}"]
    _check(
        checks,
        "no runtime bytecode packaged",
        not packaged_bytecode,
        {"packaged": packaged_bytecode, "transient_local_cache_count": len(transient_bytecode)},
    )
    if packaged_bytecode:
        failures.append("bytecode files")

    entry_errors = []
    try:
        scripts = pyproject["project"]["scripts"]
        for name, target in scripts.items():
            module_name, function_name = target.split(":", 1)
            module = importlib.import_module(module_name)
            if not callable(getattr(module, function_name, None)):
                entry_errors.append({"entrypoint": name, "target": target})
    except Exception as exc:
        entry_errors.append({"error": str(exc)})
    _check(checks, "CLI entrypoints import", not entry_errors, entry_errors)
    if entry_errors: failures.append("CLI entrypoints")

    domain = {}
    try:
        from .bridge_visual_core import resolve_start_package
        domain["start_package"] = bool(resolve_start_package().get("start_package_receipt"))
        from .rooted_crew import load_root_kernel, verify_root_kernel, load_default_crew, verify_default_crew_binding
        kernel = load_root_kernel(); domain["root_kernel"] = verify_root_kernel(kernel)["valid"]
        domain["crew_binding"] = verify_default_crew_binding(load_default_crew(), kernel)["valid"]
        from .ship_interior import validate_interior_archetype
        domain["interior"] = validate_interior_archetype()["valid"]
        from .ship_blueprint import validate_blueprint
        domain["ship_blueprint"] = validate_blueprint()["valid"]
        from .technology_core import validate_technology_registry
        domain["technology"] = not validate_technology_registry()
        from .contact_horizon import validate_contact_horizon_registry
        domain["contact_horizon"] = not validate_contact_horizon_registry()
        from .cosmic_possibility import validate_cosmic_possibility_registry
        domain["cosmic_possibility"] = not validate_cosmic_possibility_registry()
    except Exception as exc:
        domain["error"] = str(exc)
    domain_valid = bool(domain) and all(v is True for k,v in domain.items() if k != "error") and "error" not in domain
    _check(checks, "domain validators", domain_valid, domain)
    if not domain_valid: failures.append("domain validators")

    manifest_details: Any = "skipped"
    if check_manifest:
        manifest_errors = []
        output_errors = []
        try:
            manifest = json.loads((root / "PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
            expected = set(manifest["files"])
            actual = {
                p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
                and not p.relative_to(root).as_posix().startswith("output/")
                and ".git" not in p.relative_to(root).parts
                and p.relative_to(root).as_posix() not in {"PACKAGE_MANIFEST.json", "CHECKSUMS.sha256"}
                and "__pycache__" not in p.parts and p.suffix != ".pyc"
            }
            for rel in sorted(expected - actual): manifest_errors.append({"file": rel, "error": "missing"})
            for rel in sorted(actual - expected): manifest_errors.append({"file": rel, "error": "unexpected"})
            for rel in sorted(expected & actual):
                path = root / rel; info = manifest["files"][rel]
                if path.stat().st_size != info["bytes"] or _sha(path) != info["sha256"]:
                    manifest_errors.append({"file": rel, "error": "hash_or_size_mismatch"})

            output_manifest_path = root / "output/OUTPUT_SNAPSHOT_MANIFEST.json"
            output_manifest = json.loads(output_manifest_path.read_text(encoding="utf-8"))
            output_expected = set(output_manifest["files"])
            output_actual = {
                p.relative_to(root).as_posix() for p in (root / "output").rglob("*") if p.is_file()
                and p.relative_to(root).as_posix() not in {"output/OUTPUT_SNAPSHOT_MANIFEST.json", "output/OUTPUT_CHECKSUMS.sha256"}
                and "__pycache__" not in p.parts and p.suffix != ".pyc"
            }
            for rel in sorted(output_expected - output_actual): output_errors.append({"file": rel, "error": "missing"})
            for rel in sorted(output_actual - output_expected): output_errors.append({"file": rel, "error": "unexpected"})
            for rel in sorted(output_expected & output_actual):
                path = root / rel; info = output_manifest["files"][rel]
                if path.stat().st_size != info["bytes"] or _sha(path) != info["sha256"]:
                    output_errors.append({"file": rel, "error": "hash_or_size_mismatch"})
            manifest_details = {
                "canonical_checked": len(expected), "canonical_errors": manifest_errors,
                "generated_output_checked": len(output_expected), "generated_output_errors": output_errors,
            }
        except Exception as exc:
            manifest_errors.append({"error": str(exc)}); manifest_details = {"canonical_errors": manifest_errors, "generated_output_errors": output_errors}
        all_manifest_errors = manifest_errors + output_errors
        _check(checks, "strict package and output snapshots", not all_manifest_errors, manifest_details)
        if all_manifest_errors: failures.append("strict package and output snapshots")

    test_details: Any = "not requested"
    if full:
        test_env = dict(os.environ)
        test_env["PYTHONDONTWRITEBYTECODE"] = "1"
        test_env["PYTHONUTF8"] = "1"
        test_env["PYTHONIOENCODING"] = "utf-8"
        test_env["PYTHONPATH"] = str(root / "src") + (os.pathsep + test_env["PYTHONPATH"] if test_env.get("PYTHONPATH") else "")
        cp = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=root,
            env=test_env,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=120,
        )
        test_details = {"returncode": cp.returncode, "tail": cp.stdout.splitlines()[-8:]}
        _check(checks, "full automated tests", cp.returncode == 0, test_details)
        if cp.returncode: failures.append("full automated tests")

    result = {
        "schema": "axm.local-handoff-audit.v1",
        "package_root": str(root),
        "version": version,
        "full_mode": full,
        "valid": not failures,
        "failures": failures,
        "checks": checks,
    }
    result["audit_receipt"] = hashlib.sha256(canonical_json(result).encode("utf-8")).hexdigest()
    return result


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
