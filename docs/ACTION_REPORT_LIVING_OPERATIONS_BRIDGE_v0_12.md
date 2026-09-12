# Action Report — Living Operations Bridge v0.12

## Steward target

Animate the whole factual simulator in a low-graphic 3D / 2.5D style without replacing or weakening the deterministic core.

The existing bridge already had a small pseudo-3D cockpit. The missing layer was a scene projection across the registered ship interior, station map, damage-topology rehearsal routes and exterior receipt replay.

## Added

### Deterministic whole-ship scene projection

`src/axm_star_sim/low_graphic_scene.py` builds `axm.low-graphic-3d-scene.v1` from existing registries and read-only operations context.

It reuses:

- the existing `ship_interior_archetype_registry` room graph;
- the existing damage-topology station-to-room map;
- registered station roles;
- existing damage-topology repair-access routes;
- source runtime resource telemetry.

The first registered interior therefore produces a seven-room scene containing Command Deck, Central Corridor, Engineering, Research and Strategy, Mess Hall, Primary Explorer Quarters and AI Collaborator Quarters.

Room coordinates are deterministic presentation geometry derived from graph depth and stable ordering. They are explicitly **not** physical ship dimensions.

### Whole-simulator animation modes

The browser bridge gains a second scene selector independent from the existing cockpit camera:

- Director — whole simulator;
- Ship cutaway — 2.5D;
- Interior follow — 2.5D;
- Exterior replay — low-poly;
- Legacy bridge scene.

Director mode can move between cutaway, room and exterior presentation according to existing receipt phases. Selecting a failure procedure focuses its already-derived repair-access route as a **procedure drill route**, never an active-fault claim.

### Animated interior

The 480×270 framebuffer now supports:

- graph-connected isometric room blocks;
- station/crew marker animation;
- room/system activity pulses;
- current focus-room emphasis;
- procedure-drill route traversal markers;
- system binding readouts;
- explicit unresolved station-room holds.

### Exterior replay

A lightweight low-poly ship silhouette, target body and signal lane provide exterior movement without claiming ephemerides, thrust, velocity or other unavailable physical values.

### Truth boundary

The visual shell may animate, but it cannot:

- mutate runtime state;
- move authoritative crew;
- claim a procedure drill means a fault is active;
- execute an action or repair;
- clear a fault;
- exit safe state;
- apply operational release;
- restore resources;
- change truth labels;
- claim presentation coordinates are real ship geometry.

## Verification additions

New tests cover:

- deterministic scene construction;
- exact use of the registered seven-room interior;
- graph-derived layout authority labels;
- reuse of the existing station-room mapping;
- preservation of the unresolved medical-station room gap;
- rehearsal-route truth boundaries;
- input immutability;
- unknown-room fail-closed behavior;
- whole-sim scene controls/assets in the renderer;
- offline/no-Three.js rendering;
- renderer authority boundaries.

Existing v0.10/v0.11 presentation-version assertions are advanced to v0.12 without changing their semantic authority checks.

## Candidate policy

Policy ID:

`axm.low-graphic-3d-presentation-policy.candidate.v1`

Truth status:

`simulation_policy_candidate_not_canon`

## Publication gate

Publish only through the same safe reseal lane used by the prior PR #4 checkpoints:

1. assemble source candidate;
2. restore canonical read-only verifier in the reseal runner;
3. regenerate and check deterministic package seals;
4. verify canonical and generated snapshots;
5. run the full test suite;
6. run the structural handoff audit;
7. export exact seal bytes;
8. collapse temporary reseal machinery from the final tree;
9. run canonical Ubuntu + Windows CI against the exact sealed final head.

## Holds preserved

- PR #4 remains draft and unmerged.
- No direct-main write, release or CANON promotion.
- Presentation geometry remains explicitly non-physical.
- Procedure animation remains rehearsal-only unless a later authoritative live ship-state feed is explicitly connected.
- Desktop/mobile visual review remains an honest post-build hold.
