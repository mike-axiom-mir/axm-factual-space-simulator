# Local Handoff Master — v0.15.0

## What this checkpoint is

This package is the complete local continuation point after the factual ship, room, rooted crew, telemetry and competency integrations. It is deliberately self-describing so a future builder does not need this long chat to recover the architecture.

## Canonical read order

1. `MACHINE_INTAKE.json`
2. `data/local_handoff_manifest.json`
3. `LOCAL_INTAKE_HANDOFF.txt`
4. `docs/FINAL_POLISH_AUDIT_v0_15_0.md`
5. Relevant registry and module for the requested change

## Authority hierarchy

```text
immutable roots and historical commitments
→ pinned save/start identity
→ authoritative world and ship state
→ role authority and command gates
→ derived views, indexes and renderers
```

A lower layer may not silently rewrite a higher layer.

## Builder honesty protocol

A builder that lacks a browser, screenshot capability, network, model connection, compiler, simulator or required dependency records the gap using `data/builder_capability_declaration_schema.json`.

The correct result may be `partial` or `blocked`. The builder preserves verified artifacts, names unverified assumptions and requests the missing capability for a future instance. Fabricating completion is a root failure; declaring a limitation is not.

## Current factual boundaries

The ship has a simulation-grade system blueprint, not manufacturing drawings or certification. Its complete integrated mass, verified delta-v and full propulsion map remain unknown. Radiation and wellbeing are bounded operational layers, not medical or psychological diagnosis.

## Compatibility

The no-silent-rewrite migration policy protects old saves. New renderers may reconstruct them. New registries may adapt them. Meaningful semantic changes require a new version or explicit branch.

## Verification

Use the platform-safe wrapper:

- Windows: `run_local_acceptance.bat`
- Linux/macOS: `./run_local_acceptance.sh`

The wrapper verifies the canonical package, the generated-output snapshot, all domain validators and the full automated suite.

## One-command acceptance

- Windows: `run_local_acceptance.bat`
- Linux/macOS: `./run_local_acceptance.sh`

The wrappers configure the source path, disable transient bytecode, verify all managed files and run the complete handoff audit with all tests.
