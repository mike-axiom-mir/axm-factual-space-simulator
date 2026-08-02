from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from .beacons import require_verified_drand_packet

ENTROPY_SCHEMA = "axm.entropy-packet.v1"
ENTROPY_MODES = {
    "deterministic",
    "local_live",
    "mixed_live",
    "external_beacon",
    "party_commit",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def context_sha256(context: dict[str, Any]) -> str:
    return _sha256_text(f"AXM-EVENT-CONTEXT-V1|{_canonical(context)}")


def create_commitment(label: str, value: str, salt: str | None = None) -> dict[str, str]:
    label = label.strip()
    value = value.strip()
    if not label or not value:
        raise ValueError("commitment label and value cannot be empty")
    salt = salt or secrets.token_hex(24)
    commitment = _sha256_text(f"AXM-PARTY-COMMIT-V1|{label}|{value}|{salt}")
    return {
        "schema": "axm.party-reveal.v1",
        "label": label,
        "value": value,
        "salt": salt,
        "commitment": commitment,
    }


def verify_reveal(reveal: dict[str, str]) -> bool:
    required = {"label", "value", "salt", "commitment"}
    if not required.issubset(reveal):
        return False
    expected = _sha256_text(
        f"AXM-PARTY-COMMIT-V1|{reveal['label']}|{reveal['value']}|{reveal['salt']}"
    )
    return secrets.compare_digest(expected, reveal["commitment"])


@dataclass(frozen=True)
class EntropyPacket:
    schema: str
    mode: str
    created_at: str
    context_sha256: str
    combined_sha256: str
    replay_material: dict[str, Any]
    source_claim: str
    predetermined_by_master_seed: bool
    audit_notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _deterministic_component(master_seed: str, context_hash: str) -> str:
    return _sha256_text(f"AXM-DETERMINISTIC-EVENT-V1|{master_seed}|{context_hash}")


def resolve_entropy(
    *,
    mode: str,
    master_seed: str,
    context: dict[str, Any],
    beacon: dict[str, Any] | None = None,
    party_reveals: Iterable[dict[str, str]] | None = None,
    replay_packet: dict[str, Any] | None = None,
) -> EntropyPacket:
    if mode not in ENTROPY_MODES:
        raise ValueError(f"unknown entropy mode: {mode}")
    ctx_hash = context_sha256(context)

    if replay_packet is not None:
        if replay_packet.get("context_sha256") != ctx_hash:
            raise ValueError("replay packet context does not match this event")
        if replay_packet.get("mode") != mode:
            raise ValueError("replay packet mode does not match")
        return EntropyPacket(
            schema=replay_packet["schema"],
            mode=replay_packet["mode"],
            created_at=replay_packet["created_at"],
            context_sha256=replay_packet["context_sha256"],
            combined_sha256=replay_packet["combined_sha256"],
            replay_material=replay_packet["replay_material"],
            source_claim=replay_packet["source_claim"],
            predetermined_by_master_seed=bool(replay_packet["predetermined_by_master_seed"]),
            audit_notes=list(replay_packet.get("audit_notes", [])),
        )

    deterministic = _deterministic_component(master_seed, ctx_hash)
    material: dict[str, Any] = {"deterministic_component": deterministic}
    notes: list[str] = []

    if mode == "deterministic":
        combined = _sha256_text(f"AXM-ENTROPY-V1|deterministic|{ctx_hash}|{deterministic}")
        source_claim = "Reproducible pseudo-random event stream derived from the master seed and event context."
        predetermined = True
        notes.append("Best for tests and exact replays; the future is computable from the seed and context.")

    elif mode == "local_live":
        local_token = secrets.token_hex(32)
        material["local_os_token_hex"] = local_token
        combined = _sha256_text(f"AXM-ENTROPY-V1|local_live|{ctx_hash}|{local_token}")
        source_claim = "Fresh operating-system entropy sampled only when the event was resolved."
        predetermined = False
        notes.append("Not derivable from the master seed. The stored token makes the resolved event replayable afterward.")
        notes.append("A device owner could still reroll by discarding an unwanted result unless authority rules prevent it.")

    elif mode == "mixed_live":
        local_token = secrets.token_hex(32)
        material["local_os_token_hex"] = local_token
        combined = _sha256_text(
            f"AXM-ENTROPY-V1|mixed_live|{ctx_hash}|{deterministic}|{local_token}"
        )
        source_claim = "Master-seed context mixed with fresh operating-system entropy at event resolution."
        predetermined = False
        notes.append("Preserves campaign identity while keeping the exact future outside the original seed.")
        notes.append("The local authority can still reroll unless the append-only ledger is enforced.")

    elif mode == "external_beacon":
        if not beacon:
            raise ValueError("external_beacon mode requires a beacon packet")
        if beacon.get("provider") != "drand-quicknet":
            raise ValueError("this runtime currently accepts only cryptographically verified drand-quicknet packets")
        verification = require_verified_drand_packet(beacon)
        random_value = str(beacon["randomness"]).strip().lower()
        provider = "drand-quicknet"
        round_id = int(beacon["round"])
        material["beacon"] = {
            "provider": provider,
            "round": round_id,
            "randomness": random_value,
            "signature": beacon.get("signature"),
            "packet_sha256": beacon.get("packet_sha256"),
            "chain_hash": (beacon.get("chain") or {}).get("chain_hash"),
            "source_url": beacon.get("source_url"),
            "verification": {
                "status": verification["status"],
                "valid": verification["valid"],
                "scheme_id": verification["cryptographic"]["scheme_id"],
                "method": verification["cryptographic"]["method"],
            },
        }
        combined = _sha256_text(
            f"AXM-ENTROPY-V1|external_beacon|{ctx_hash}|{provider}|{round_id}|{random_value}"
        )
        source_claim = "Cryptographically verified public drand quicknet randomness mixed with the event context."
        predetermined = False
        notes.append("AXM refuses unverified beacon packets; structural checks alone are not accepted as entropy authority.")
        notes.append("For multiplayer fairness, commit to a future round before its value is known.")

    else:  # party_commit
        reveals = sorted(list(party_reveals or []), key=lambda item: item.get("label", ""))
        if len(reveals) < 2:
            raise ValueError("party_commit mode requires at least two reveal packets")
        invalid = [item.get("label", "<unknown>") for item in reveals if not verify_reveal(item)]
        if invalid:
            raise ValueError(f"invalid party reveal(s): {invalid}")
        material["party_reveals"] = reveals
        reveal_mix = "|".join(
            f"{item['label']}:{item['commitment']}:{item['value']}:{item['salt']}" for item in reveals
        )
        combined = _sha256_text(f"AXM-ENTROPY-V1|party_commit|{ctx_hash}|{reveal_mix}")
        source_claim = "Multiple committed party contributions combined after reveal verification."
        predetermined = False
        notes.append("No single honest participant can know the final mix before all hidden contributions are revealed.")
        notes.append("A participant can still abort instead of revealing; this starter does not solve abort fairness.")

    return EntropyPacket(
        schema=ENTROPY_SCHEMA,
        mode=mode,
        created_at=datetime.now(timezone.utc).isoformat(),
        context_sha256=ctx_hash,
        combined_sha256=combined,
        replay_material=material,
        source_claim=source_claim,
        predetermined_by_master_seed=predetermined,
        audit_notes=notes,
    )


def roll(packet: EntropyPacket | dict[str, Any], label: str) -> float:
    combined = packet.combined_sha256 if isinstance(packet, EntropyPacket) else packet["combined_sha256"]
    digest = hashlib.sha256(f"AXM-ROLL-V1|{combined}|{label}".encode("utf-8")).digest()
    return int.from_bytes(digest, "big") / ((1 << (8 * len(digest))) - 1)


def create_master_seed_receipt(
    mode: str,
    phrase: str | None = None,
    beacon: dict[str, Any] | None = None,
    party_reveals: Iterable[dict[str, str]] | None = None,
) -> dict[str, Any]:
    phrase = (phrase or "").strip()
    context = {"purpose": "master-seed-genesis", "phrase": phrase}
    packet = resolve_entropy(
        mode=mode,
        master_seed=phrase or "AXM-OPEN-FUTURE",
        context=context,
        beacon=beacon,
        party_reveals=party_reveals,
    )
    resolved_seed = f"AXM-{packet.combined_sha256[:24].upper()}"
    return {
        "schema": "axm.master-seed-receipt.v1",
        "resolved_seed": resolved_seed,
        "phrase_present": bool(phrase),
        "phrase_sha256": _sha256_text(phrase) if phrase else None,
        "entropy": packet.to_dict(),
        "honesty": "Once resolved, this receipt reproduces the same initial universe. Future events can still use deferred live entropy.",
    }
