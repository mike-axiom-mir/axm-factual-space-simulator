# Action Report — Living Operations Bridge v0.14

## Steward analysis

v0.12 created the whole-ship 2.5D shell and v0.13 made the registered interior feel alive. Three visual gaps remained:

1. exterior spacecraft motion was still mostly decorative rather than tied to the declared ship modules and system functions;
2. director mode switched scenes from broad playback phase but did not carry an explicit, hashable shot plan tied to immutable cue segments;
3. the growing renderer had no explicit visual-detail control for weaker devices.

v0.14 addresses all three without adding simulation authority.

## Improvement 1 — Exterior operations capability layer

`src/axm_star_sim/exterior_operations_animation.py` derives read-only visual actors from the existing ship blueprint, 2.5D scene, source resource snapshot, failure procedures and immutable event cues.

Declared exterior roles include:

- power arrays;
- thermal rejection;
- main propulsion;
- reaction control;
- communications;
- external sensors;
- docking/EVA;
- robotics/probe operations.

The renderer can therefore show array tracking, radiator shimmer, propulsion plumes, RCS puffs, antenna sweeps, sensor cones, docking alignment, EVA tether silhouettes, robotic-arm motion and probe-deployment ghosts.

These are **capability/rehearsal actors**. No live thrust, docking, EVA, probe deployment or robotics movement is inferred from their animation.

## Improvement 2 — Causal cinematic director

`src/axm_star_sim/causal_cinematic_director.py` creates a deterministic shot plan for every imported immutable cue.

Each cue preserves the source segment order and source display fractions:

`command_outbound → observation_window → telemetry_return`

The default shot language is:

- command context → bridge;
- observation context → exterior/target;
- telemetry return → relevant interior room based on the recorded state-change receipt.

The director cannot reorder events, retarget events, alter cue timing fractions, change source values or execute operations.

## Improvement 3 — Visual detail profiles

The renderer gains:

- `eco`;
- `standard`;
- `rich`.

The setting only changes presentation density such as particle/trail budgets and secondary actor motion. It cannot change simulation calculations or facts.

## Browser controls

New controls:

- Exterior choreography: Director / Systems / Communications / Docking / EVA / Probe;
- Causal cinematic director toggle;
- Visual detail: Eco / Standard / Rich.

Docking, EVA and probe selections are explicitly labelled rehearsal views.

## Truth boundaries

The v0.14 renderer may animate declared capabilities and route camera shots, but it may not:

- claim physical vehicle dimensions or exact hardware geometry;
- claim an exterior operation is active;
- execute an exterior operation;
- apply thrust;
- dock;
- begin EVA;
- deploy a probe;
- move authoritative robotics or crew;
- reorder events;
- change cue timing fractions;
- retarget an event;
- modify resources or world state;
- change truth labels.

## Verification additions

Tests cover:

- exact reuse of declared blueprint modules/systems;
- no invented external execution state;
- deterministic exterior actor construction;
- procedure tracks staying rehearsal-only;
- source resource values copied without inference;
- cue choreography staying presentation-only;
- cinematic segment order and display-fraction preservation;
- telemetry room focus from recorded state-change receipts;
- renderer controls and authority flags;
- offline 480×270 rendering.

## Governance

Policy ID:

`axm.exterior-cinematic-presentation-policy.candidate.v1`

Truth status:

`simulation_policy_candidate_not_canon`

PR #4 remains draft/unmerged. No main write, release or CANON promotion is included.
