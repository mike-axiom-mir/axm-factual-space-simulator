# Action report — v0.1.0

## Built

- local Python reference implementation;
- deterministic named seed branches;
- generated star and planetary systems;
- derived orbit, temperature, flux, gravity and escape values;
- truth-layer schema;
- source and formula registries;
- immutable source snapshot pattern;
- NASA Exoplanet Archive and JPL SBDB download adapters;
- party-directed causal opportunity selection;
- self-contained interactive HTML cockpit visualization;
- JSON, JSONL and SHA-256 manifests;
- tests, stress validation and demo outputs.

## Verified

- identical seeds produce identical canonical physical state when timestamps are excluded;
- different seeds produce different systems;
- all derived values declare formulas;
- all hypotheses include limitation notes;
- planet orbits increase outward;
- output files receive SHA-256 hashes;
- generated HTML contains the complete embedded system state;
- eight automated tests pass;
- 250 generated systems pass stress validation.

## Not claimed complete

- research-grade astrophysics;
- N-body stability;
- atmospheric or biological simulation;
- live source update inside this build environment;
- native game-engine integration;
- complete bridge interaction;
- AI crew runtime.

## Next strongest action

Use a real NASA Exoplanet Archive snapshot to calibrate the offline priors while preserving detection-bias warnings and versioned source hashes.
