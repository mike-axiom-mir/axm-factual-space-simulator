# Verification report — AXM Factual Star Adventure Simulator v0.1.0

Verified on 2026-08-02 using Python 3.13 in the build container.

## Automated tests

Eight tests passed:

- deterministic same-seed generation;
- different-seed separation;
- ordered outward orbits;
- truth-layer validation;
- all evidence source IDs registered;
- output package and embedded HTML state creation;
- bounded and encoded NASA/JPL request builders;
- pinned mock snapshot normalization and catalog summary pipeline.

## Stress validation

250 deterministic systems were generated and validated:

- planet count range: 3–8;
- average planet count: 5.344;
- all systems passed truth and orbit validation;
- all four current adventure opportunity families appeared across the run.

## Viewer checks

- generated HTML embeds the complete system JSON locally;
- generated JavaScript passed Node syntax validation;
- no external network resources are required by the viewer.

## Environment limitation

The live NASA and JPL download calls could not be executed inside the artifact container because outbound DNS/network access was unavailable. Their official endpoint structure was researched, request builders were tested, and the downstream snapshot pipeline was tested with pinned mock data. A real local machine with internet should run the update commands before the first empirical calibration pass.

## No-fake-done boundary

This verifies the reference generator, provenance pipeline, output contract and first visualizer. It does not verify research-grade orbital stability, atmospheric climate, biology, N-body dynamics, native game-engine rendering or AI crew gameplay.
