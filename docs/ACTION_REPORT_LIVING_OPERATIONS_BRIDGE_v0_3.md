# Action Report — Living Operations Bridge v0.3

## Steward goal

Turn the Phase 1 Living Bridge into a more coherent operations simulation surface instead of merely adding more decorative animation.

## Preserved

- Living Bridge v0.2 source and demo remain bundled for rollback/comparison.
- 480×270 internal framebuffer and nearest-neighbour scaling.
- deterministic crew idle system;
- graph/radar/ops console animation;
- receipt-attention lights;
- command/science/telemetry ambient lighting;
- hologram, star, planet and causal signal animation;
- reduced-motion gate;
- presentation-only authority.

## v0.3 additions

### 1. Causal director

`Director · causal choreography` is the new default view. It does not choose actions. It changes only the presentation camera:

- outbound command → bridge view;
- observation window → hologram focus;
- telemetry return → window focus.

Manual Bridge / Window / Hologram views remain available.

### 2. Station focus and crew choreography

The active replay phase deterministically selects a presentation focus:

- early outbound command → command;
- later outbound command → navigation;
- observation → science;
- telemetry → engineering, returning command attention late in the receipt.

Focused crew and consoles receive stronger motion/emphasis. This is **receipt reenactment**, not a claim that an autonomous crew member performed a canonical action.

### 3. Receipt-pattern hologram

The immutable outcome ID selects a bounded visual pattern:

- constraint;
- repeatable;
- coupling;
- ambiguous;
- neutral fallback.

This alters hologram geometry only. It does not change interpretation text or assign hidden success/failure values.

### 4. Real runtime context

A new deterministic adapter summarizes the source runtime for presentation:

- reactor reserve;
- sensor health;
- hull integrity;
- fuel and heat;
- open causal threads;
- current dynamic action menu.

Actions are **inspect only**. The renderer exposes `mayExecuteAction: false` and `mayCloseThread: false` alongside the existing no-world-write gates.

The detached demo context is a bounded extract from PR #3's Expedition Alpha runtime state at commit `96944abe2ddfd96107a9ef167ff52f80e8d3986d`. The repository integration builder reads the real runtime file directly instead of trusting the demo extract.

## Verification completed here

- all Python tests: **24 / 24 PASS** (includes retained v0.2 regression tests);
- retained v0.2 Node runtime: **33 / 33 PASS**;
- v0.3 Node runtime: **42 / 42 PASS**;
- v0.3 includes a **1,200-frame steward soak** with receipt changes;
- source mission time remained `3.0 h` throughout the soak;
- action execution, resource mutation and mission-time authority remained false;
- standalone v0.3 rebuild: PASS.

## Honest hold

Pixel-level desktop/mobile appearance is not claimed as verified in this runtime. The previous Chromium capture seam remains unresolved. Runtime/canvas behavior is verified through the deterministic Node harness, not through a reviewed image capture.

## Integration gate

Do not copy generated HTML into canon as a substitute for source integration. In a reviewed PR #3 worktree or successor:

1. add `living_operations_bridge.py`;
2. add `living_operations_bridge_view.py`;
3. use `build_living_operations_bridge_from_repo.py` against the real Expedition Alpha snapshot;
4. visually inspect desktop/mobile motion;
5. reseal the repository;
6. refresh generated-output receipts;
7. run full local acceptance;
8. generate/review the digest-locked PR plan;
9. publish only through the draft-PR lane after Mike's merge gate.
