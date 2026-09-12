# Public capability discovery

The Factual Star Adventure Simulator can expose one deliberately bounded capability to local AXM discovery tools without making discovery an execution or adoption authority.

## Exported capability

`axm.factual-space-simulator.seeded-local-adventure`

The declaration covers only the checkout-independent installed-wheel path for:

```text
axm-star-sim generate --seed <seed> --output <dir>
axm-star-sim verify-ledger --output <dir>
```

Those two operations are local, account-free, network-free, dependency-free at runtime, and use the canonical read-only registries packaged into the wheel. This declaration does **not** classify network-capable commands such as `fetch-beacon` or `update-sources` as offline operations.

The transfer artifact is the verified reproducible-wheel path supplied by `tools/build_reproducible_wheel.py`. Building a wheel does not publish it.

## Deterministic source binding

`tools/generate_public_capabilities.py` derives the public record from exact repository evidence and refuses drift that would change the claimed boundary without review. It checks:

- the explicit `.axm/discovery-public.json` opt-in;
- package name, version, Python floor, zero runtime dependencies, license declaration and `axm-star-sim` entrypoint in `pyproject.toml`;
- the actual CLI source still declaring `generate` and `verify-ledger`;
- the reproducible-wheel receipt and false release/merge/CANON authority contract;
- the Apache-2.0 license evidence.

The generated receipt records byte count, SHA-256 and Git-blob SHA-1 for each source used by the declaration. Those hashes prove content identity relative to the selected source tree; they are not signatures and do not authenticate authorship.

This Python implementation adapts the already-tested public marker + generated registry + Discovery Buddy bridge pattern from `mike-axiom-mir/axm-anomaly-garden` PR #10 at exact head `583f95dcccf830cf13d29be0e3eb1a0647937a5f`. No Anomaly Garden runtime code is copied.

Regenerate after a deliberate contract change:

```text
python tools/generate_public_capabilities.py --write
python tools/reseal_package.py --write
```

Verify without mutation:

```text
python tools/generate_public_capabilities.py --check
python -m unittest -v tests.test_public_capability_discovery
python tools/reseal_package.py --check
```

## Discovery Buddy bridge

Public discovery requires the explicit marker above. A compatible Discovery Buddy can then scan the repository and return this capability as `DISCOVERY_EVIDENCE_ONLY`.

A match means only that the selected source declares the bounded contract and that the discovery evidence parsed correctly. Discovery Buddy does not install the wheel, execute `axm-star-sim`, select the capability for a user, release a package, merge a branch, or declare CANON.

The dedicated CI bridge proves both sides separately: it installs the simulator wheel into a clean external virtual environment and executes the real generate/verify loop offline, then uses the pinned portable Discovery Buddy scanner/query artifact to locate the declaration. Discoverability is therefore not treated as runtime proof by itself.

## Status and authority

The capability record exports `status: null` because this package boundary does not currently carry a dedicated maturity/status field suitable for discovery. The generator refuses to invent `WORKING`, `TEST`, release readiness, or another classification.

Mike remains the merge/CANON authority. Public discovery adds no automatic installation, execution, selection, release, merge, history rewrite, or CANON authority.
