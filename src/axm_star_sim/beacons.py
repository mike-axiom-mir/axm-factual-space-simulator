from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DRAND_LATEST_URL = "https://api.drand.sh/v2/beacons/quicknet/rounds/latest"
DRAND_QUICKNET_CHAIN = {
    "provider": "drand-quicknet",
    "chain_hash": "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971",
    "public_key": "83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a",
    "period_seconds": 3,
    "genesis_time": 1692803367,
    "scheme_id": "bls-unchained-g1-rfc9380",
    "signature_group": "BLS12-381 G1",
    "public_key_group": "BLS12-381 G2",
    "dst": "BLS_SIG_BLS12381G1_XMD:SHA-256_SSWU_RO_NUL_",
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _is_hex(value: str, expected_chars: int) -> bool:
    if len(value) != expected_chars:
        return False
    try:
        bytes.fromhex(value)
    except ValueError:
        return False
    return value.lower() == value


def _canonical_packet_material(packet: dict[str, Any]) -> dict[str, Any]:
    chain = packet.get("chain") or DRAND_QUICKNET_CHAIN
    return {
        "provider": packet.get("provider"),
        "round": packet.get("round"),
        "randomness": packet.get("randomness"),
        "signature": packet.get("signature"),
        "previous_signature": packet.get("previous_signature"),
        "chain_hash": chain.get("chain_hash"),
        "public_key": chain.get("public_key"),
        "scheme_id": chain.get("scheme_id"),
    }


def packet_sha256(packet: dict[str, Any]) -> str:
    body = json.dumps(_canonical_packet_material(packet), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def validate_drand_structure(packet: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    provider = str(packet.get("provider", ""))
    if provider != "drand-quicknet":
        failures.append("provider must be drand-quicknet")

    try:
        round_number = int(packet.get("round"))
        if round_number < 1:
            failures.append("round must be a positive integer")
    except (TypeError, ValueError):
        round_number = 0
        failures.append("round must be a positive integer")

    randomness = str(packet.get("randomness", "")).strip().lower()
    signature = str(packet.get("signature", "")).strip().lower()
    previous = packet.get("previous_signature")
    if not _is_hex(randomness, 64):
        failures.append("randomness must be 32-byte lowercase hexadecimal")
    if not _is_hex(signature, 96):
        failures.append("quicknet signature must be 48-byte lowercase hexadecimal")
    if previous not in (None, ""):
        failures.append("quicknet is unchained and must not contain previous_signature")

    chain = packet.get("chain")
    if not isinstance(chain, dict):
        failures.append("pinned quicknet chain metadata is missing")
        chain = {}
    for field in ("chain_hash", "public_key", "scheme_id", "period_seconds", "genesis_time", "dst"):
        if chain.get(field) != DRAND_QUICKNET_CHAIN[field]:
            failures.append(f"quicknet chain field mismatch: {field}")

    randomness_hash_valid = False
    if _is_hex(signature, 96) and _is_hex(randomness, 64):
        randomness_hash_valid = hashlib.sha256(bytes.fromhex(signature)).hexdigest() == randomness
        if not randomness_hash_valid:
            failures.append("randomness does not equal SHA-256(signature)")

    recorded_packet_hash = packet.get("packet_sha256")
    packet_hash_valid = recorded_packet_hash in (None, packet_sha256(packet))
    if not packet_hash_valid:
        failures.append("packet_sha256 does not match packet material")

    return {
        "schema": "axm.drand-structural-verification.v1",
        "valid": not failures,
        "round": round_number,
        "randomness_hash_valid": randomness_hash_valid,
        "packet_hash_valid": packet_hash_valid,
        "failures": failures,
        "checks": [
            "provider and positive round",
            "quicknet 48-byte G1 signature encoding length",
            "32-byte randomness encoding length",
            "unchained packet shape",
            "pinned chain hash/public key/scheme/DST",
            "randomness = SHA-256(signature)",
            "AXM packet material hash",
        ],
        "honesty": "Structural and hash validation is not a BLS signature verification.",
    }


def _verifier_paths(verifier_dir: Path | None = None) -> tuple[Path, Path]:
    directory = verifier_dir or (_project_root() / "tools" / "drand_verifier")
    return directory, directory / "verify.mjs"


def verify_drand_packet(
    packet: dict[str, Any],
    *,
    verifier_dir: Path | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    structural = validate_drand_structure(packet)
    result: dict[str, Any] = {
        "schema": "axm.drand-verification.v1",
        "provider": "drand-quicknet",
        "round": packet.get("round"),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "structural": structural,
        "cryptographic": {
            "attempted": False,
            "valid": False,
            "method": "pinned-node-noble-bls12-381",
            "scheme_id": DRAND_QUICKNET_CHAIN["scheme_id"],
            "dependency_versions": {"@noble/curves": "1.6.0", "@noble/hashes": "1.5.0"},
        },
        "valid": False,
        "status": "structural_invalid" if not structural["valid"] else "verifier_unavailable",
    }
    if not structural["valid"]:
        return result

    directory, script = _verifier_paths(verifier_dir)
    node = os.environ.get("AXM_NODE_BINARY") or shutil.which("node")
    dependencies_present = (
        (directory / "node_modules" / "@noble" / "curves" / "package.json").exists()
        and (directory / "node_modules" / "@noble" / "hashes" / "package.json").exists()
    )
    if not node or not script.exists() or not dependencies_present:
        result["cryptographic"]["reason"] = (
            "Node verifier dependencies are not installed. Run tools/drand_verifier/install.sh or install.bat."
        )
        return result

    result["cryptographic"]["attempted"] = True
    payload = {
        "round": int(packet["round"]),
        "randomness": str(packet["randomness"]),
        "signature": str(packet["signature"]),
        "public_key": DRAND_QUICKNET_CHAIN["public_key"],
        "scheme_id": DRAND_QUICKNET_CHAIN["scheme_id"],
        "dst": DRAND_QUICKNET_CHAIN["dst"],
    }
    try:
        completed = subprocess.run(
            [node, str(script)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            cwd=directory,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["status"] = "verifier_error"
        result["cryptographic"]["reason"] = str(exc)
        return result

    if completed.returncode not in (0, 1):
        result["status"] = "verifier_error"
        result["cryptographic"]["reason"] = completed.stderr.strip() or "verifier exited unexpectedly"
        return result
    try:
        verifier_result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        result["status"] = "verifier_error"
        result["cryptographic"]["reason"] = "verifier did not return JSON"
        result["cryptographic"]["stderr"] = completed.stderr.strip()
        return result

    result["cryptographic"].update(verifier_result)
    crypto_valid = bool(verifier_result.get("valid"))
    result["valid"] = structural["valid"] and crypto_valid
    result["status"] = "cryptographically_verified" if result["valid"] else "cryptographic_invalid"
    return result


def require_verified_drand_packet(packet: dict[str, Any], *, verifier_dir: Path | None = None) -> dict[str, Any]:
    verification = verify_drand_packet(packet, verifier_dir=verifier_dir)
    if not verification["valid"]:
        reason = verification["status"]
        detail = verification.get("cryptographic", {}).get("reason")
        if detail:
            reason = f"{reason}: {detail}"
        raise ValueError(f"drand packet is not cryptographically verified ({reason})")
    return verification


def normalize_drand_packet(
    raw: dict[str, Any],
    source_url: str = DRAND_LATEST_URL,
    *,
    verifier_dir: Path | None = None,
) -> dict[str, Any]:
    randomness = str(raw.get("randomness", "")).strip().lower()
    signature = str(raw.get("signature", "")).strip().lower()
    if not randomness:
        raise ValueError("drand response contains no randomness")
    if not signature:
        raise ValueError("drand response contains no signature")
    if raw.get("round") is None:
        raise ValueError("drand response contains no round")
    packet: dict[str, Any] = {
        "schema": "axm.external-beacon-packet.v2",
        "provider": "drand-quicknet",
        "round": int(raw["round"]),
        "randomness": randomness,
        "signature": signature,
        "previous_signature": raw.get("previous_signature"),
        "chain": dict(DRAND_QUICKNET_CHAIN),
        "source_url": source_url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }
    packet["packet_sha256"] = packet_sha256(packet)
    verification = verify_drand_packet(packet, verifier_dir=verifier_dir)
    packet["verification"] = verification
    packet["verification_status"] = verification["status"]
    return packet


def fetch_drand_latest(output: Path, *, verifier_dir: Path | None = None) -> Path:
    request = urllib.request.Request(
        DRAND_LATEST_URL,
        headers={"User-Agent": "AXM-Factual-Star-Simulator/0.4"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = json.loads(response.read().decode("utf-8"))
    packet = normalize_drand_packet(raw, verifier_dir=verifier_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    return output
