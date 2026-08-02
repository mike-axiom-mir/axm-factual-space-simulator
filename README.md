# AXM Factual Star Adventure Simulator v0.15.0

**Mike — Axiom/Mir**

A local-first, deterministic and evidence-bounded space-adventure simulator. The current checkpoint joins an open factual universe, blind possibility forging, persistent expeditions, a lived-in ship, immutable rooted crew reasoning, a 22-system spacecraft blueprint, 78 crew-station metrics and evidence-gated skill evolution.

## Open first

1. Open `OPEN_LOCAL_HANDOFF.html`.
2. Read `START_HERE.txt`.
3. Run the one-command local acceptance check:
   - Windows: `run_local_acceptance.bat`
   - Linux/macOS: `./run_local_acceptance.sh`

The package requires no internet or external AI for normal local play, verification or reconstruction.

## Non-negotiable core

1. **Truth / Source Truth**
2. **Continuity / No-Loss**
3. **Agency / No Takeover**
4. **Wisdom over Speed**

Root commitment: `01e6c42e4cfc6d8b7ea7999ddf9c29282d6d19722ef934d7c2e9ca095911a8f5`

Roots shape option eligibility before efficiency. They cannot be reordered, disabled, outvoted or silently migrated.

## Current architecture

- Deterministic initial universes with live-entropy options that fail closed.
- Four explicit command modes.
- Physics-coupled measurements and causal action threads.
- Source-pinned technology lineages with unknown performance kept unknown.
- Long-horizon contact search without guaranteed aliens.
- Persistent revision-safe expedition atlas.
- Blind hidden-scenario forge with pre-play commitments.
- Offline-first save slots.
- Versioned bridge grammar and lived-in ship interior.
- Deterministic crew continuity and command recall.
- 22 interconnected ship systems and typed failure propagation.
- 78 truth-labelled telemetry metrics and six crew-station views.
- Evidence-gated role competency growth.
- No-silent-rewrite save migration policy.
- Builder capability-gap declarations instead of fake completion.

## Main local demonstrations

- `output/crew_station_metric_demo/crew_station_console.html`
- `output/factual_ship_blueprint_demo/ship_blueprint_console.html`
- `output/ship_interior_demo/ship_interior_console.html`
- `output/rooted_crew_demo/rooted_crew_console.html`
- `output/bridge_visual_core_demo/paint_foundation_bridge.html`
- `output/adventure_slot_demo/slot_manager.html`
- `output/persistent_atlas_demo/atlas.html`
- `output/contact_horizon_demo/contact_horizon_console.html`

## Useful commands

```text
Windows tests:          run_tests.bat
Linux/macOS tests:      ./run_tests.sh
Windows acceptance:     run_local_acceptance.bat
Linux/macOS acceptance: ./run_local_acceptance.sh
Windows demos:          run_demo.bat
Linux/macOS demos:      ./run_demo.sh
Windows seal check:     run_package_seal_check.bat
Linux/macOS seal check: ./run_package_seal_check.sh
```

For the safe reseal and promotion sequence, read `docs/PORTABILITY_AND_PACKAGE_MAINTENANCE.md`.

## GitHub improvements

Routine future changes use the digest-locked draft-PR lane in `docs/GITHUB_PR_LANE.md`. It verifies and hashes locally, refuses direct-main pushes and opens a draft pull request only after the exact plan digest is reviewed.

```text
Plan only: run_github_pr_plan.bat
Publish:   run_github_pr_publish.bat <reviewed-plan-digest>
```

The wrappers set `PYTHONPATH` and disable transient bytecode generation. Advanced users may alternatively run `python -m pip install -e . --no-deps` and then use the registered `axm-*` commands.

## Truth boundary

This package is not a flight-certified spacecraft, not proof of alien life, not a validated medical or psychology model and not a weapon-construction package. Integrated mass, verified delta-v and complete propulsion performance remain unknown.

## Local continuation

Read `docs/LOCAL_HANDOFF_MASTER_v0_15_0.md` and `docs/FUTURE_POTENTIAL_ROADMAP_v1.md`. New builders must declare unavailable capabilities using `data/builder_capability_declaration_schema.json` rather than pretending a requested tool or result exists.
