# Verification Report — v0.15.0

## Automated suite

- Tests passed: 218
- New local-handoff and migration tests: 18
- Pre-manifest architecture audit: PASS
- Audit checks: 11

## Repaired regressions

- Ship-interior visual entry page restored and builder-safe.
- Rooted-crew visual entry page restored and builder-safe.
- v0.14 reproducible builder and stress scripts present.
- README, START_HERE and LOCAL_INTAKE_HANDOFF identify v0.15.0.

## Retained deep station stress

- Ship states: 300
- Telemetry cards: 23400
- Station views: 1800
- Learning-pressure snapshots: 2100
- Failures: 0

## Final packaging

The final build additionally performs strict managed-file verification, full handoff audit, ZIP extraction and the complete test suite from the extracted package.

## Honest boundary

The package is a verified simulation checkpoint, not proof of multi-year runtime stability or a flight-certified spacecraft.

## Independent local-package recheck

- Added platform-safe one-command acceptance wrappers.
- Repaired aggregate demo reconstruction and preserved all promised HTML entrypoints.
- Generated summary paths are package-relative.
- Canonical files and generated-output snapshots now have separate integrity manifests.
- Timestamp-bearing demo rebuilds refresh their output snapshot instead of pretending to be byte-identical.

## Final rechecked package layout

- Canonical source/data/docs/tests/templates tracked: 254 files
- Generated output snapshot tracked: 168 files
- Full tests after demo rebuild: 218 passed
- Full handoff audit after demo rebuild: PASS
- All promised demo entrypoints present: PASS
- Container-specific paths in generated outputs: none
