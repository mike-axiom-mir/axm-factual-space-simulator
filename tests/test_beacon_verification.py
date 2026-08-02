from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from axm_star_sim.beacons import (
    DRAND_QUICKNET_CHAIN,
    normalize_drand_packet,
    packet_sha256,
    validate_drand_structure,
    verify_drand_packet,
)
from axm_star_sim.entropy import resolve_entropy

# Signature published in the official drand quicknet documentation for round 42.
ROUND_42_SIGNATURE = "95a9f9f5b231b7714de1553105d8ffdf3dcda24cfdb1e689319bccf79a9c8ce430a91b811fbfaf763900bc998b5d686a"
ROUND_42_RANDOMNESS = hashlib.sha256(bytes.fromhex(ROUND_42_SIGNATURE)).hexdigest()


def packet_42() -> dict:
    packet = {
        "schema": "axm.external-beacon-packet.v2",
        "provider": "drand-quicknet",
        "round": 42,
        "randomness": ROUND_42_RANDOMNESS,
        "signature": ROUND_42_SIGNATURE,
        "previous_signature": None,
        "chain": dict(DRAND_QUICKNET_CHAIN),
        "source_url": "official-fixture",
        "retrieved_at": "2026-08-02T00:00:00+00:00",
    }
    packet["packet_sha256"] = packet_sha256(packet)
    return packet


class DrandVerificationTests(unittest.TestCase):
    def test_official_round_fixture_passes_all_structural_hash_checks(self) -> None:
        result = validate_drand_structure(packet_42())
        self.assertTrue(result["valid"], result)
        self.assertTrue(result["randomness_hash_valid"])
        self.assertTrue(result["packet_hash_valid"])
        self.assertIn("not a BLS", result["honesty"])

    def test_signature_or_randomness_tampering_is_rejected(self) -> None:
        broken = packet_42()
        broken["randomness"] = "00" * 32
        result = validate_drand_structure(broken)
        self.assertFalse(result["valid"])
        self.assertFalse(result["randomness_hash_valid"])

    def test_chain_metadata_tampering_is_rejected(self) -> None:
        broken = packet_42()
        broken["chain"]["public_key"] = "00" * 96
        broken["packet_sha256"] = packet_sha256(broken)
        result = validate_drand_structure(broken)
        self.assertFalse(result["valid"])
        self.assertTrue(any("public_key" in row for row in result["failures"]))

    def test_verifier_unavailable_is_never_called_verified(self) -> None:
        with TemporaryDirectory() as temp:
            result = verify_drand_packet(packet_42(), verifier_dir=Path(temp))
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "verifier_unavailable")
        self.assertFalse(result["cryptographic"]["attempted"])

    def test_node_verifier_result_controls_cryptographic_status(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "node_modules/@noble/curves").mkdir(parents=True)
            (root / "node_modules/@noble/hashes").mkdir(parents=True)
            (root / "node_modules/@noble/curves/package.json").write_text('{}', encoding="utf-8")
            (root / "node_modules/@noble/hashes/package.json").write_text('{}', encoding="utf-8")
            (root / "verify.mjs").write_text('// mocked by subprocess', encoding="utf-8")
            completed = type("Completed", (), {
                "returncode": 0,
                "stdout": json.dumps({"valid": True, "bls_signature_valid": True, "randomness_hash_valid": True}),
                "stderr": "",
            })()
            with patch("axm_star_sim.beacons.shutil.which", return_value="node"), patch(
                "axm_star_sim.beacons.subprocess.run", return_value=completed
            ) as mocked:
                result = verify_drand_packet(packet_42(), verifier_dir=root)
            self.assertTrue(result["valid"])
            self.assertEqual(result["status"], "cryptographically_verified")
            sent = json.loads(mocked.call_args.kwargs["input"])
            self.assertEqual(sent["round"], 42)
            self.assertEqual(sent["public_key"], DRAND_QUICKNET_CHAIN["public_key"])

    def test_external_entropy_refuses_unverified_packet(self) -> None:
        with patch("axm_star_sim.entropy.require_verified_drand_packet", side_effect=ValueError("no BLS")):
            with self.assertRaises(ValueError):
                resolve_entropy(
                    mode="external_beacon",
                    master_seed="SAME",
                    context={"event": 1},
                    beacon=packet_42(),
                )

    def test_external_entropy_accepts_only_after_cryptographic_verification(self) -> None:
        verified = {
            "status": "cryptographically_verified",
            "valid": True,
            "cryptographic": {
                "scheme_id": DRAND_QUICKNET_CHAIN["scheme_id"],
                "method": "pinned-node-noble-bls12-381",
            },
        }
        with patch("axm_star_sim.entropy.require_verified_drand_packet", return_value=verified):
            entropy = resolve_entropy(
                mode="external_beacon",
                master_seed="SAME",
                context={"event": 1},
                beacon=packet_42(),
            )
        self.assertFalse(entropy.predetermined_by_master_seed)
        self.assertEqual(entropy.replay_material["beacon"]["verification"]["status"], "cryptographically_verified")

    def test_normalizer_never_promotes_structural_validation_to_crypto(self) -> None:
        raw = {"round": 42, "randomness": ROUND_42_RANDOMNESS, "signature": ROUND_42_SIGNATURE}
        with TemporaryDirectory() as temp:
            packet = normalize_drand_packet(raw, verifier_dir=Path(temp))
        self.assertEqual(packet["verification_status"], "verifier_unavailable")
        self.assertFalse(packet["verification"]["valid"])


if __name__ == "__main__":
    unittest.main()
