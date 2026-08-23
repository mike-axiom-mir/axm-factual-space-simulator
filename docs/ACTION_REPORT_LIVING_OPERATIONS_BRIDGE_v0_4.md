# Living Operations Bridge v0.4 — Bridge Rehearsal

## Status

Draft candidate on PR #4. The rehearsal layer maps already-imported source actions into deterministic station/role planning rehearsals. It never executes a source action and never converts rehearsal completion into an observed outcome.

## Capability

- Select an existing source action from the living operations context.
- Build a deterministic station route from the action category.
- Surface evidence requirements and explicit hold points.
- Mark light-time, radiation, and evidence-discrimination context only when grounded in the imported action text.
- End at a command-authority request, not execution.

## Authority boundary

The rehearsal may change selected action, rehearsal step, station focus, ghost route, evidence/hold display, and crew presentation choreography.

It may not execute an action, mutate runtime state/resources, advance mission time, append/retarget events, close causal threads, change truth labels, or claim an outcome.

## Focused verification

Before GitHub publication in the working chat:
- `tests/test_bridge_rehearsal.py`: 6/6 PASS.
- v0.4 JavaScript extension: `node --check` PASS.
- new/modified Python source syntax: PASS.

Repository-local deterministic seal and complete CI are separate gates.
