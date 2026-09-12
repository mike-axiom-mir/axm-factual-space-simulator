from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


MARKER_SCHEMA = "axm.discovery-public/v1"
CAPABILITY_SCHEMA = "axm.public-capability/v1"
RECEIPT_SCHEMA = "axm.public-capability-receipt/v1"
REPO = "mike-axiom-mir/axm-factual-space-simulator"
PACKAGE_NAME = "axm-factual-star-adventure-simulator"
PACKAGE_VERSION = "0.15.0"
PYTHON_REQUIREMENT = ">=3.10"
CAPABILITY_ID = "axm.factual-space-simulator.seeded-local-adventure"
REGISTRY_PATH = Path("registry/capabilities.jsonl")
RECEIPT_PATH = Path("registry/capabilities.receipt.json")
SOURCE_PATHS = (
    Path(".axm/discovery-public.json"),
    Path("pyproject.toml"),
    Path("src/axm_star_sim/cli.py"),
    Path("tools/build_reproducible_wheel.py"),
    Path("tools/generate_public_capabilities.py"),
    Path("LICENSE"),
)


class DiscoveryContractError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _hold(code: str, message: str) -> DiscoveryContractError:
    return DiscoveryContractError(code, message)


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _git_blob_sha1(payload: bytes) -> str:
    prefix = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(prefix + payload).hexdigest()


def _regular_file(root: Path, relative: Path) -> Path:
    root = root.resolve()
    candidate = root / relative
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise _hold("SOURCE_SYMLINK", f"refusing symlinked discovery source: {relative.as_posix()}")
    if not candidate.is_file():
        raise _hold("SOURCE_MISSING", f"required discovery source is missing: {relative.as_posix()}")
    return candidate


def _read_bytes(root: Path, relative: Path) -> bytes:
    return _regular_file(root, relative).read_bytes()


def _read_utf8(root: Path, relative: Path) -> str:
    try:
        return _read_bytes(root, relative).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _hold("SOURCE_NOT_UTF8", f"source is not UTF-8: {relative.as_posix()}") from exc


def _parse_marker(root: Path) -> dict[str, Any]:
    try:
        marker = json.loads(_read_utf8(root, SOURCE_PATHS[0]))
    except json.JSONDecodeError as exc:
        raise _hold("PUBLIC_MARKER_INVALID", "public discovery marker is not valid JSON") from exc
    expected = {
        "schema": MARKER_SCHEMA,
        "public": True,
        "repo": REPO,
        "display_name": "AXM Factual Star Adventure Simulator",
    }
    if marker != expected:
        raise _hold("PUBLIC_MARKER_DRIFT", "public discovery marker requires explicit review")
    return marker


def _toml_sections(text: str) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    current = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            sections.setdefault(current, {})
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        sections.setdefault(current, {})[key.strip()] = value.strip()
    return sections


def _toml_string(raw: str | None, field: str) -> str:
    if raw is None:
        raise _hold("PACKAGE_METADATA_DRIFT", f"missing pyproject field: {field}")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _hold("PACKAGE_METADATA_DRIFT", f"unsupported pyproject string form: {field}") from exc
    if not isinstance(value, str):
        raise _hold("PACKAGE_METADATA_DRIFT", f"pyproject field is not a string: {field}")
    return value


def _validate_package_contract(root: Path) -> dict[str, str]:
    sections = _toml_sections(_read_utf8(root, Path("pyproject.toml")))
    project = sections.get("project", {})
    scripts = sections.get("project.scripts", {})
    observed = {
        "name": _toml_string(project.get("name"), "project.name"),
        "version": _toml_string(project.get("version"), "project.version"),
        "requires_python": _toml_string(project.get("requires-python"), "project.requires-python"),
        "command": _toml_string(scripts.get("axm-star-sim"), "project.scripts.axm-star-sim"),
    }
    expected = {
        "name": PACKAGE_NAME,
        "version": PACKAGE_VERSION,
        "requires_python": PYTHON_REQUIREMENT,
        "command": "axm_star_sim.cli:main",
    }
    if observed != expected:
        raise _hold("PACKAGE_IDENTITY_DRIFT", f"review required for package identity drift: {observed!r}")
    if project.get("dependencies") != "[]":
        raise _hold("PACKAGE_DEPENDENCY_DRIFT", "discovered offline capability requires zero runtime dependencies")
    if project.get("license") != '{file = "LICENSE"}':
        raise _hold("PACKAGE_LICENSE_DRIFT", "package license declaration changed")
    return observed


def _validate_cli_contract(root: Path) -> list[str]:
    cli_text = _read_utf8(root, Path("src/axm_star_sim/cli.py"))
    try:
        tree = ast.parse(cli_text, filename="src/axm_star_sim/cli.py")
    except SyntaxError as exc:
        raise _hold("CLI_PARSE_FAILURE", "axm-star-sim CLI source did not parse") from exc
    commands: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "add_parser":
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            commands.add(first.value)
    required = {"generate", "verify-ledger"}
    if not required.issubset(commands):
        raise _hold("CLI_CONTRACT_DRIFT", f"required offline commands missing: {sorted(required - commands)}")
    return sorted(commands)


def _validate_reproducible_builder(root: Path) -> None:
    source = _read_utf8(root, Path("tools/build_reproducible_wheel.py"))
    required_fragments = (
        'RECEIPT_SCHEMA = "axm.reproducible-wheel-build-receipt.v1"',
        '"rebuilds_compared": 2',
        '"release": False',
        '"merge": False',
        '"canon": False',
    )
    missing = [fragment for fragment in required_fragments if fragment not in source]
    if missing:
        raise _hold("REPRODUCIBLE_BUILD_CONTRACT_DRIFT", "reproducible wheel evidence contract changed")


def _validate_license(root: Path) -> None:
    license_text = _read_utf8(root, Path("LICENSE"))
    if "Apache License" not in license_text or "Version 2.0, January 2004" not in license_text:
        raise _hold("LICENSE_DRIFT", "Apache-2.0 license evidence changed")


def _source_evidence(root: Path) -> list[dict[str, Any]]:
    evidence = []
    for relative in SOURCE_PATHS:
        payload = _read_bytes(root, relative)
        evidence.append(
            {
                "path": relative.as_posix(),
                "bytes": len(payload),
                "sha256": _sha256(payload),
                "git_blob_sha1": _git_blob_sha1(payload),
            }
        )
    return evidence


def build_capability(root: Path) -> dict[str, Any]:
    root = root.resolve()
    _parse_marker(root)
    _validate_package_contract(root)
    _validate_cli_contract(root)
    _validate_reproducible_builder(root)
    _validate_license(root)
    return {
        "schema": CAPABILITY_SCHEMA,
        "id": CAPABILITY_ID,
        "version": PACKAGE_VERSION,
        "summary": "Generate and replay-verify a seeded local factual-space adventure from the self-contained installed wheel.",
        "providers": [REPO],
        "consumers": [],
        "status": None,
        "license": "Apache-2.0",
        "runtime": {
            "kind": "python-package",
            "minimumVersion": "3.10",
            "dependencies": [],
            "networkRequired": False,
            "accountRequired": False,
        },
        "entrypoints": {
            "package": PACKAGE_NAME,
            "command": "axm-star-sim",
        },
        "operations": ["generate", "verify-ledger"],
        "contracts": {
            "generate": "axm-star-sim generate --seed <seed> --output <dir>",
            "verify": "axm-star-sim verify-ledger --output <dir>",
            "scope": "seeded local generation plus deterministic ledger replay verification only",
            "excludedNetworkOperations": ["fetch-beacon", "update-sources"],
            "transferArtifact": "reproducible wheel from tools/build_reproducible_wheel.py",
        },
        "determinism": {
            "seededGeneration": True,
            "ledgerReplayVerification": True,
            "reproducibleWheelBuilder": True,
        },
        "source": {
            "package": "pyproject.toml",
            "command": "src/axm_star_sim/cli.py",
            "reproducibleBuild": "tools/build_reproducible_wheel.py",
            "license": "LICENSE",
            "publicMarker": ".axm/discovery-public.json",
        },
        "authority": {
            "discoveryOnly": True,
            "execution": False,
            "automaticInstall": False,
            "automaticSelection": False,
            "packagePublication": False,
            "release": False,
            "merge": False,
            "canon": False,
        },
    }


def build_outputs(root: Path) -> tuple[bytes, bytes]:
    capability = build_capability(root)
    registry = _canonical_json(capability)
    receipt_body = {
        "schema": RECEIPT_SCHEMA,
        "capability_id": CAPABILITY_ID,
        "record": {
            "bytes": len(registry),
            "sha256": _sha256(registry),
        },
        "sources": _source_evidence(root),
        "pattern_provenance": {
            "kind": "adapted-public-discovery-pattern",
            "source_repo": "mike-axiom-mir/axm-anomaly-garden",
            "source_pr": 10,
            "source_head": "583f95dcccf830cf13d29be0e3eb1a0647937a5f",
            "adaptation": "Python package metadata, CLI AST, reproducible-wheel evidence and factual-simulator authority boundaries; no provider runtime code copied.",
        },
        "authority": {
            "discovery_only": True,
            "execution": False,
            "installation": False,
            "release": False,
            "merge": False,
            "canon": False,
        },
    }
    return registry, _canonical_json(receipt_body)


def write_outputs(root: Path) -> None:
    registry, receipt = build_outputs(root)
    output_dir = (root / "registry").resolve()
    root = root.resolve()
    if output_dir.exists() and output_dir.is_symlink():
        raise _hold("OUTPUT_SYMLINK", "registry output directory may not be a symlink")
    output_dir.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH_ABS = root / REGISTRY_PATH
    RECEIPT_PATH_ABS = root / RECEIPT_PATH
    for path, payload in ((REGISTRY_PATH_ABS, registry), (RECEIPT_PATH_ABS, receipt)):
        if path.exists() and path.is_symlink():
            raise _hold("OUTPUT_SYMLINK", f"generated output may not be a symlink: {path.name}")
        path.write_bytes(payload)


def verify_outputs(root: Path) -> None:
    expected_registry, expected_receipt = build_outputs(root)
    for relative, expected in ((REGISTRY_PATH, expected_registry), (RECEIPT_PATH, expected_receipt)):
        path = _regular_file(root, relative)
        actual = path.read_bytes()
        if actual != expected:
            raise _hold("GENERATED_OUTPUT_DRIFT", f"generated discovery output drifted: {relative.as_posix()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate or verify the public capability record for the factual simulator.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        if args.write:
            write_outputs(args.root)
        else:
            verify_outputs(args.root)
    except DiscoveryContractError as exc:
        print(json.dumps({"status": "HOLD", "code": exc.code, "message": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps({"status": "PASS", "capability": CAPABILITY_ID, "mode": "write" if args.write else "check"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
