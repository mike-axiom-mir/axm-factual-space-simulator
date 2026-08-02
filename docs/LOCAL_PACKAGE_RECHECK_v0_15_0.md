# Local Package Recheck — v0.15.0

## Reason

The complete local handoff was independently extracted and tested again. The package itself contained no Python bytecode, but the original documented sequence could create local `__pycache__` files before the handoff audit and cause a false audit failure. Direct `python -m axm_star_sim...` commands also assumed an editable install or manually configured source path.

## Repairs

- Handoff bytecode validation now checks the package manifest rather than transient runtime caches.
- Embedded audit tests disable bytecode generation.
- All top-level run wrappers disable bytecode generation.
- Added `run_tests.bat` and `run_tests.sh`.
- Added one-command `run_local_acceptance.bat` and `run_local_acceptance.sh`.
- README, START_HERE, machine intake and handoff manifest now use platform-safe commands.
- Runtime requirements are explicit: Python 3.10+, zero required Python dependencies, no internet or external AI for normal local operation.
- The drand BLS verifier remains clearly optional and separately dependency-pinned.

## Acceptance target

A fresh extraction must pass archive integrity, strict package hashes, all automated tests, all domain validators, CLI imports, reference checks, and the full handoff audit using the one-command wrapper.

## Demonstration rebuild repair

A second reconstruction check found that the aggregate demo builder could stop at the bridge visual layer and that some later deterministic builders deleted their own HTML entry pages. Canonical offline entry templates are now stored under `assets/demo_templates/`; every relevant builder restores its entry page, and the aggregate builder fails if any promised demo entrypoint is absent. Generated summary paths are package-relative rather than container-specific.

## Generated-output integrity policy

Some truthful demo files contain creation timestamps, so rebuilding them is replay-valid but not necessarily byte-identical. Canonical source, rules, data, tests, templates and documentation are therefore protected by `PACKAGE_MANIFEST.json`, while the currently shipped or freshly rebuilt demos are protected by `output/OUTPUT_SNAPSHOT_MANIFEST.json`. The demo builder refreshes the output snapshot automatically, so package verification remains meaningful before and after a deliberate demo rebuild.
