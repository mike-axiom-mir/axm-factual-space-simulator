# Temporal Evidence Bridge Candidate — v0.15.0 baseline / renderer v0.14.0

## Status

This is an isolated chat-built candidate validated against the existing
`mike-axiom-mir/axm-factual-space-simulator` main checkpoint. It is not a
GitHub merge, release, or automatic version promotion.

## Open

`output/temporal_bridge_candidate/temporal_bridge.html`

The demo replays four immutable Expedition Alpha event receipts through a
continuous `requestAnimationFrame` renderer. It visualizes:

- compressed simulation-prior orbital geometry;
- outbound command transit;
- an observation window;
- delayed telemetry return;
- a source-authoritative mission clock distinct from disposable replay time;
- reconciled per-receipt mission-time ranges and deltas to the ledger head;
- explicit historical/head, unknown-age and no-future-receipt indicators;
- a continuous replay scrubber plus previous/next receipt controls;
- overview, target-focus and signal-lane inspect-only cameras;
- inspect-any-known-object facts and framing without retargeting the event;
- focus, all and minimal label-density modes;
- truth-labelled resource-delta receipts with direction-only color semantics;
- current read-only runtime resources;
- exact source event hashes and truth labels.

The renderer derives receipt ranges only when every recorded
`outcome.resource_deltas.mission_time_hours` value reconciles to the current
runtime mission clock. Missing or inconsistent time data produces
`HOLD_TEMPORAL_RECONSTRUCTION`; it does not fabricate event timestamps.

Recorded `outcome.resource_deltas` are separately converted into deterministic
read-only state-change receipts. Each bar compares a resource only with that
same resource's largest absolute change in the imported ledger. Cyan means
increase and violet means decrease; the renderer assigns no good/bad judgment
and cannot write the displayed delta back into runtime state.

## Existing architecture reused

- `bridge_visual_core.make_reconstruction_packet`
- `bridge_render_profile_registry.json`
- `axm.output-manifest.v3`
- immutable event-chain links
- renderer/world-state authority separation
- main package reseal and local acceptance

The new `axm.render.temporal-evidence-bridge.v1` profile declares
`changes_semantics: false`. Its authorization packet permits animation while
forbidding historical-state changes. Scrubbing, camera, inspector and label
presets are declared as presentation state and cannot alter world state,
history, event targets, runtime resources or truth labels.

## Verification completed in the isolated candidate

- selected input hashes matched the existing output manifest;
- four event links and the runtime ledger head matched;
- tampered bytes and broken links were held;
- continuous animation advanced under a bounded DOM/canvas runtime harness;
- source mission time stayed fixed while replay display time advanced;
- replay scrubbing reached receipt boundaries without advancing source time;
- camera and label presets accepted only registered values and fell back safely;
- object inspection followed only registered planets and could not retarget events;
- state-change receipts preserved source order, units and direction without value judgment;
- the ledger-head receipt ended exactly at the source mission clock;
- missing wall-clock timestamps remained visibly unknown;
- reduced motion blocked playback;
- 22 focused adapter/view tests passed;
- 49 of 49 bounded DOM/canvas runtime checks passed;
- the full main suite passed 248 of 248 tests after output refresh and reseal;
- 283 canonical files and 175 generated outputs passed strict snapshot checks.

Focused verification commands:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest tests.test_temporal_renderer_adapter tests.test_temporal_bridge_view
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python scripts/temporal_bridge_runtime_smoke_v0_14.py
```

## Honest hold

No legitimate live capture path could open this local surface in the working
runtime: the local Chromium executable is unset. A prior cloud-browser attempt
also rejected the local data URL under its URL safety policy. No frame was
captured in either case. Motion cadence, responsive layout and visual quality remain
`UNKNOWN_MISSING_VISUAL_CAPTURE`, even though the bounded runtime contract
passes. The candidate must not be merged until those checks, a version
decision, the normal digest-locked PR plan and Mike's approval are complete.
