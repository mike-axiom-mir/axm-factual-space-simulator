# AXM Factual Star Adventure Simulator v0.6.0 — Verification Report

**Date:** 2026-08-02  
**Result:** PASS WITH DECLARED LIMITS

## Automated test suite

Command:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Result:

```text
Ran 66 tests
OK
```

Coverage includes:

- deterministic generation and truth layers;
- source and formula registration;
- four command modes;
- open-future entropy receipts;
- public-beacon fail-closed behavior;
- physics expectation versus realized measurement;
- orbital, sensor, thermal, radiation, communication, and trajectory state;
- dynamic causal-thread menus;
- technology-core selection and explicit unknowns;
- long-horizon contact registry validation;
- step-100,000 gate behavior;
- absence of hidden seed-level contact truth;
- active-transmission refusal before evidence and governance gates;
- replay integrity for contact-search events;
- rejection of an early-unlock registry mutation.

## Stress verification

Command:

```bash
PYTHONPATH=src python scripts/stress_verify_v0_6.py
```

Result: `PASS`

### Technology selection

- Population: 1,000 seeds
- Eligible equal slots: 4
- Distribution:
  - Blue Moon pathfinder lineage: 262
  - Gateway platform lineage: 247
  - Orion crew-transport lineage: 241
  - Starship HLS pathfinder lineage: 250
- Unpublished propulsion performance promoted: `false`

The observed counts are not required to be identical. The verified property is that every eligible core occupies one equal catalog slot without hidden weighting and all four are reached.

### Ordinary expedition runtime

- Systems: 250
- Turns per system: 12
- Events replay-verified: 3,000
- Dynamic menu size: 3–9
- All six action categories appeared.
- All five outcome classes appeared.

### Long-horizon contact runtime

- Initial contact states checked: 250
- Master seeds that preselected alien/contact truth: 0
- Contact-search actions before step 100,000: 0
- Late-horizon trials: 80
- Late-horizon events replay-verified: 80
- Stage after one dedicated search:
  - search eligible: 49
  - candidate anomaly: 31
- Single searches confirming external agency: 0

This verifies that the threshold unlocks a search process rather than a guaranteed encounter.

### Deterministic reproducibility

- Independent campaign pairs: 30
- Turns per pair: 10
- Result: identical decisions, outcomes, causal state, and event hashes for each pair.

## Browser artifact checks

Report: `docs/browser_script_check_v0_6_0.json`

- HTML files checked: 17
- JavaScript blocks checked with `node --check`: 16
- Embedded JSON blocks parsed: 5
- Failures: 0

## Public-name scan

The package was scanned case-insensitively for the removed franchise name and associated fictional-system labels. No matches remain in source, data, documentation, or generated output.

## Package integrity

The final package uses:

- `PACKAGE_MANIFEST.json` for file sizes and SHA-256 hashes;
- `CHECKSUMS.sha256` for independent checksum inspection;
- `verify_package.py` for local validation;
- a post-extraction test and manifest-verification pass.

The final ZIP hash is recorded in the delivery response after packaging.

## What this verification does not prove

- It does not prove extraterrestrial life exists.
- It does not estimate a true frequency of alien life or civilization.
- It does not validate any specific candidate biosignature or technosignature.
- It does not establish that the evidence ladder is a universal scientific standard.
- It does not prove the simulator covers all false positives or all possible forms of life, intelligence, or technology.
- It does not make a fictional or philosophical hypothesis empirical.
- It does not replace external scientific peer review or real contact governance.
- It does not claim the optional drand BLS pairing ran unless the pinned verifier dependencies are installed and the verifier reports cryptographic success.

## Acceptance statement

Within its declared scope, v0.6.0 correctly enforces:

```text
late eligibility ≠ guaranteed encounter
anomaly ≠ life
technological pattern ≠ living agency
advanced capability ≠ hostile intent
information ≠ usable innovation
seeded universe ≠ predetermined future
```
