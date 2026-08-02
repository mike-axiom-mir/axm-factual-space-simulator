# AXM Action Report — v0.4.0 Physics and Causal Growth

## Requested repairs

1. Replace constrained generic runtime outcome templates with outcomes connected to sensor noise, radiation, orbital phase, thermal load, communication delay, and probe trajectories.
2. Replace the fixed initial action set with new actions generated from causal threads opened during play.
3. Close the previously declared drand verification gap without pretending a checksum is a BLS signature check.

## Completed

### Runtime physics

Implemented `physics_runtime.py` with:

- Kepler equation solver and time-varying orbital geometry;
- incident stellar flux;
- component-level detector noise and expected SNR;
- separate entropy-resolved measurement noise;
- radiative spacecraft thermal balance;
- relative radiation/electronics operations index;
- light-time and transmission-delay calculations;
- Hohmann reference transfer time and delta-v;
- persistent probe launch/arrival records;
- physics-driven probability and resource modifiers.

### Causal growth

Implemented `thread_engine.py` with:

- persistent parent/child causal threads;
- evidence and visit tracking;
- action generation per thread type;
- condition-driven engineering actions;
- inventory-aware probe filtering;
- deterministic ranking and deduplication;
- 3–9 action menu bounds;
- explicit mission continuation when all threads close.

### Replay integrity

Events now preserve and verify:

- pre-entropy physics;
- selected dynamic action record;
- adjusted probability snapshot;
- entropy rolls;
- realized measurement;
- opened threads;
- regenerated next menu;
- state-after hash.

### drand trust boundary

Implemented:

- pinned quicknet identity;
- packet schema v2;
- encoding and chain-metadata checks;
- `SHA-256(signature)` randomness validation;
- optional isolated BLS12-381 Node verifier;
- exact noble dependency pins and lock-file integrity values;
- strict rejection of unverified packets;
- `fetch-beacon` and `verify-beacon` CLI paths;
- official round-42 fixture.

## Repair discovered during stress testing

The first 3,600-event run found that one campaign could provisionally resolve every active thread and produce an empty menu at turn 11. This was not accepted as finished.

The repair added a deterministic mission-continuation layer with evidence review, system survey, and maintenance options. A dedicated regression test now protects this path.

## Result

The runtime no longer chooses a generic story template first and adds science wording afterward. Physics and ship state now shape the probability space before entropy, and the result grows the next set of physically relevant choices.
