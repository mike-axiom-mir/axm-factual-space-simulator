# Intake polish receipt

Date: 2026-08-02  
Working lane: `working-v0.15.0-intake1`

## Preserved source

The received handoff ZIP and the exact extracted v0.15.0 snapshot were not modified. The source ZIP was recorded with SHA-256:

`ed06dd27ac2a1b417c3a7cf2d3e210c21f67aff369c9f342ded911a2e16971e1`

All changes described here were made in a separate intake working lane.

## Bounded improvements

- Added a deterministic, check-first package sealer with explicit `--write` mode.
- Made Windows and POSIX launchers resolve their own package directory and request UTF-8 explicitly.
- Made the full handoff audit's child test process decode output as UTF-8.
- Rejected adventure-slot directory escapes, including overwrite through a directory symlink.
- Rebuilt the local human doorway with responsive navigation across all eight subsystem consoles.
- Labeled concept artwork explicitly so it cannot be mistaken for live simulation telemetry.
- Added maintenance guidance and static tests for offline links, launcher portability and package sealing.

## Evidence boundaries

Package integrity, deterministic behavior and automated acceptance are separate claims and are checked separately. The local doorway was structurally verified from its HTML and linked files. Live visual rendering was not claimed because this task's browser policy did not permit opening the local `file://` artifact.

## Final verification

The completed polish lane passed these independent gates before promotion:

- 224 automated tests completed: 223 passed and one Windows symlink fixture was skipped because the current user does not hold symlink-creation privilege.
- 262 canonical package files passed strict manifest and checksum verification.
- 168 generated output files passed their separate snapshot verification.
- The full handoff audit passed version, JSON, syntax, path, entrypoint, domain-validator, package and test checks.
- A held-out seed check reproduced identical simulation semantics for the same seed, changed them for a different seed and replay-verified the resulting event. The wall-clock `generated_at` receipt was intentionally excluded from the semantic comparison.

Held-out semantic system SHA-256: `f613bdf877c3e1e952ba297506a43c9b940114140989e18ce9d2247958a4ee08`  
Held-out replayed event SHA-256: `57378ecfdf0678815d55c7e0e4c31ae4298a4d02bf87c0aabbff7b57b68b6784`

The machine-readable package and handoff-audit results are reproduced by `run_local_acceptance.bat` and `run_package_seal_check.bat`. Re-run both after any deliberate package change.
