# drand Quicknet Verification Boundary

## Rule

AXM does not accept a public-randomness packet because it contains plausible-looking fields. `external_beacon` entropy currently accepts only drand quicknet packets that pass both structural checks and BLS12-381 signature verification.

## Pinned quicknet identity

```text
chain hash:
52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971

scheme:
bls-unchained-g1-rfc9380

period:
3 seconds

signature group:
BLS12-381 G1, 48-byte compressed signature

public-key group:
BLS12-381 G2, 96-byte compressed public key

RFC 9380 DST:
BLS_SIG_BLS12381G1_XMD:SHA-256_SSWU_RO_NUL_
```

The full public key is pinned in `src/axm_star_sim/beacons.py` and copied into every normalized packet.

## Verification sequence

1. Require provider `drand-quicknet` and a positive integer round.
2. Require a 32-byte lowercase hexadecimal randomness value.
3. Require a 48-byte lowercase hexadecimal signature.
4. Reject `previous_signature`, because quicknet is unchained.
5. Compare every pinned chain field.
6. Verify `randomness == SHA-256(signature)`.
7. Build the unchained message as `SHA-256(uint64_be(round))`.
8. Hash that message to BLS12-381 G1 with the pinned RFC 9380 DST.
9. Verify the pairing equation against the pinned G2 public key.
10. Only then return `cryptographically_verified`.

Structural checks explicitly state that they are not BLS verification.

## Isolated verifier

The BLS implementation lives under `tools/drand_verifier` and is optional. It uses exact pinned versions:

```text
@noble/curves 1.6.0
@noble/hashes 1.5.0
```

Install with `npm ci`, using the included lock file and integrity hashes. The physics, causal, command, and deterministic entropy roots do not depend on Node or noble.

## Failure behaviour

- missing Node or dependencies → `verifier_unavailable`;
- malformed packet → `structural_invalid`;
- invalid pairing or randomness hash → `cryptographic_invalid`;
- verifier crash or invalid output → `verifier_error`.

All four states are rejected as external entropy. There is no fallback that quietly treats structural validation as cryptographic truth.

## Included fixture

`data/beacon_fixtures/drand_quicknet_round_42.json` preserves the official quicknet round-42 signature used in drand documentation. In the build container it passes every structural and randomness-hash check. The package deliberately records `verifier_unavailable` until the pinned Node dependencies are installed.

## Execution boundary in this build

The Python adapter, strict rejection path, packet hashing, official fixture checks, mocked successful subprocess contract, tamper failures, and verifier JavaScript syntax were tested.

The build environment had no outbound package-registry access, so the two pinned npm packages could not be installed there. Therefore this report does **not** claim that the round-42 BLS pairing was executed inside the build container. After local `npm ci`, run:

```bash
python -m axm_star_sim verify-beacon \
  --input data/beacon_fixtures/drand_quicknet_round_42.json \
  --write-back
```

Only a returned status of `cryptographically_verified` permits the packet to enter an AXM entropy event.
