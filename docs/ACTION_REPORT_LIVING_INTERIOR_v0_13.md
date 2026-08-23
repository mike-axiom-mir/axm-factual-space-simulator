# Action Report — Living Interior Animation v0.13

## Steward finding

v0.12 successfully established a whole-simulator 480×270 low-graphic 2.5D shell, but most rooms still behaved like animated boxes. The next useful visual layer is not heavier 3D; it is making the existing registered interior feel inhabited and operational while retaining strict presentation authority.

## Added

### Deterministic living-interior contract

`src/axm_star_sim/living_interior_animation.py` derives animation actors only from the existing v0.12 scene projection, room graph, system bindings, copied runtime resources and failure-procedure rehearsal routes.

It produces:

- room-specific ambient activity profiles for all registered rooms;
- one presentation portal actor for every registered room-graph edge;
- procedure-role crew reenactment tracks over existing repair-access paths;
- a camera-only walkthrough that traverses the registered graph;
- copied read-only resource visual channels for relevant rooms.

### Room-specific life

Room types now receive distinct low-pixel visual language:

- command: console/status/map sweeps;
- corridor/transit: guide-light and portal motion;
- engineering: abstract equipment, maintenance, thermal and power-status motion;
- research: hologram, sensor and evidence sweeps;
- mess/crew-life: service/environment ambience;
- personal quarters: low ambient/artifact motion;
- machine quarters: compute/activity sweeps.

These are abstract visual actors, not physical hardware replicas.

### Portals and traversal

Every registered graph edge receives a presentation portal animation. During a selected procedure drill, the current rehearsal edge can visibly open while a role-labelled reenactment marker traverses the pinned room route.

This does **not** create authoritative door state or crew location.

### Renderer controls

The bridge adds an `Interior life` selector with:

- Director / context driven;
- Ambient life;
- Systems focus;
- Procedure route focus.

The existing 480×270 framebuffer, offline rendering, reduced-motion support and v0.12 whole-ship camera modes remain intact.

## Authority boundary

The renderer may animate presentation actors only. It may not:

- open an authoritative door;
- move authoritative crew;
- claim abstract machinery is the ship's real hardware geometry;
- convert a drill into active-fault truth;
- execute a repair or action;
- modify resources/runtime;
- advance mission time;
- change truth labels.

## Verification target

The v0.13 lane must pass deterministic reseal, canonical/generated snapshot checks, the full automated suite on Ubuntu and Windows, and the structural handoff audit.

The PR remains draft. No merge, main write, release or CANON promotion is part of this run.
