# Action Report — Living Operations Bridge v0.15

## Steward target

Improve interaction quality after v0.14 without turning the growing animated presentation into a command-heavy UI or a second simulator.

The v0.14 bridge already had living interiors, exterior capability actors, a causal cinematic director and visual-detail controls. The remaining gap was that a user could watch those layers but could not easily say **show me this room / station / system / module and keep following it**.

## Added

### Deterministic interactive exploration contract

`src/axm_star_sim/interactive_exploration.py` builds `axm.interactive-exploration-presentation.v1` from the already-generated scene/interior/exterior/cinematic contracts.

Selectable presentation targets include:

- every registered room;
- every pinned station;
- unresolved station mappings as explicit HOLD targets;
- unique interior system bindings;
- graph-edge presentation portals;
- declared exterior system capability actors;
- declared ship modules.

Each target carries source-backed inspection metadata, a presentation scene/focus hint and explicit non-authority flags.

### Follow modes

The browser adds four presentation follow modes:

- Causal director;
- Selected target;
- Active procedure;
- Active event.

Selecting a room/system/module changes camera/UI focus only. Active-procedure follow reuses the existing procedure reenactment target. Active-event follow leaves the immutable event replay/director in control.

### Touch-friendly room selection

In ship-cutaway mode, tapping/clicking close to a registered room selects that room and switches the explorer to selected-target follow.

The hit test uses existing presentation coordinates; it does not modify the room graph, physical geometry or authoritative crew location.

### Source-backed inspector

The renderer gains a compact inspector showing the selected target's existing metadata, such as:

- room type / adjacency / system bindings;
- station role bindings / placement authority;
- portal endpoints / registered travel-time authority;
- interior system-bound rooms;
- exterior system role / category / criticality / declared functions;
- module functions / contained rooms / geometry authority.

Unresolved mappings remain visible as HOLDs instead of being silently filled in.

### Mobile usability

Previous/next target buttons receive larger mobile touch targets and the explorer catalog is grouped by target kind. The main internal framebuffer remains 480×270 and the renderer remains dependency-free/offline.

## Truth / authority boundary

Explorer selection may:

- change presentation target;
- change presentation follow mode;
- inspect declared metadata;
- move the presentation camera/focus;
- highlight a selected target.

It may **not**:

- change authoritative selection/state;
- retarget an immutable event;
- move authoritative crew or robotics;
- open an authoritative door;
- execute actions, repairs or exterior operations;
- change resources;
- advance mission time;
- claim physical geometry/hardware;
- change truth labels.

Policy:

`axm.interactive-exploration-presentation-policy.candidate.v1`

Truth status:

`simulation_policy_candidate_not_canon`

## Verification additions

New tests cover:

- deterministic target catalog construction;
- unique target IDs;
- room/station/system/portal/exterior/module target coverage;
- unresolved medical-station mapping remaining a HOLD;
- follow modes remaining presentation-only;
- input immutability;
- no target gaining world/action/operation/crew/robotics/event authority;
- renderer explorer/follow controls;
- pointer/touch room selection;
- runtime authority flags;
- continued offline 480×270 rendering.

Existing presentation-version assertions advance to v0.15 while preserving their original safety/authority checks.

## Publication gate

Use the same PR #4 safe reseal lane:

1. publish one atomic candidate tree;
2. restore canonical read-only verifier inside reseal job before generating seals;
3. reseal/recheck;
4. verify canonical/generated snapshots;
5. run full tests;
6. run structural handoff audit;
7. export exact seal bytes;
8. fold exact seals into a clean final tree;
9. remove temporary export files and restore canonical verifier;
10. run final Windows + Ubuntu canonical CI against the exact sealed head.

## Holds preserved

- PR #4 stays draft and unmerged.
- No direct-main write, release or CANON promotion.
- Selection and following remain presentation-only.
- Unresolved mappings remain explicit rather than guessed.
- Desktop/mobile visual feel remains an honest human review hold.
