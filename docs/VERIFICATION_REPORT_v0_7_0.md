# AXM Factual Star Adventure Simulator
## Verification Report v0.7.0 — Persistent Expedition Atlas

Status: **PASS — tested foundation**

## Automated unit and integration suite

Command:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Result:

- 77 tests passed;
- 0 failures;
- 0 errors.

Atlas-specific coverage includes:

- starter catalog and policy validation;
- real landmark stability across unrelated master seeds;
- explicit procedural-frontier classification;
- append-only visit-chain verification and tamper rejection;
- multi-system atlas merge and route creation;
- revisit packet immutability;
- catalog-revision immutability;
- display-only proper-motion propagation;
- normalized catalog import without automatic cross-release identity merging;
- atlas output generation and runtime-event updates.

## Stress verification

Command:

```bash
PYTHONPATH=src python scripts/stress_verify_v0_7.py
```

Result:

- 240 complete generated systems;
- 10 turns per system;
- 2,400 events replay-verified;
- 240 visit chains verified;
- 60 multi-system atlas merges;
- 60 route records;
- 120 revisit packets checked;
- source-pinned landmark hashes remained stable across seeds;
- no generated frontier coordinate was promoted to catalog fact;
- no route line was promoted to ship capability;
- no future render revision mutated visit history.

Observed generated frontier distance range:

```text
65.804722 to 1796.847693 light-years
```

This range verifies generator behavior only. It is not presented as a calibrated Milky Way population model.

## Demonstration package

The demonstration builder produced:

- one shared persistent atlas;
- 6 mapped locations;
- 2 route records;
- 10 hash-chained visits;
- 2 independently generated frontier expeditions;
- 2 render-reconstruction packets for one historical expedition;
- a valid complete visit chain.

The later reconstruction changes visual and asset-engine identifiers while retaining authoritative location, event, observation, and visit hashes.

## Browser artifact validation

- 31 HTML files parsed;
- 37 script blocks checked;
- 30 JavaScript blocks passed `node --check`;
- 7 embedded JSON blocks parsed;
- 0 failures.

## Package integrity

The final package is checked using:

```bash
python verify_package.py
```

`PACKAGE_MANIFEST.json` records byte sizes and SHA-256 hashes for all managed package files. `CHECKSUMS.sha256` provides a plain-text equivalent.

The final ZIP is extracted into a clean directory and the test suite and package verifier are run again before release.

## Honest limits

- The bundled factual starter atlas has four landmarks only: the Solar System, Proxima Centauri, TRAPPIST-1, and 51 Pegasi.
- No full live Gaia or NASA Exoplanet Archive bulk download was performed inside this build environment.
- A normalized append-only catalog importer is implemented, but source-specific high-volume download/normalization jobs remain future work.
- Cross-release identity matching has an explicit receipt policy but no automated probabilistic matcher yet.
- Simple parallax inversion is used only for the nearby demonstration anchors where the supplied uncertainty is small; it is not a general distance estimator.
- Linear proper-motion propagation is display-only and must not drive precision navigation.
- Solar System precision geometry still requires pinned JPL Horizons or SPICE products.
- The atlas display is a simple projection rather than a complete three-dimensional Galactic navigation environment.
- Generated frontier coordinates are stable simulation anchors, not claims that uncatalogued real stars exist there.
- Selecting an old destination does not prove any current ship can physically reach it.

## Verification conclusion

v0.7.0 establishes a tested no-rewrite map foundation:

```text
factual catalog skeleton
+ explicit uncertainty
+ clearly labelled procedural frontier
+ append-only expedition history
+ revision-safe future visualization
```
