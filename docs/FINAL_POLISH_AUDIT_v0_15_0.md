# Final Polish Audit — v0.15.0

## Actual issues found and repaired

- The root README still identified the package as v0.6.0.
- START_HERE and LOCAL_INTAKE_HANDOFF still opened as v0.8.0.
- Two documented visual entry pages were missing because their deterministic demo builders deleted their folders but did not recreate the HTML.
- The pyproject description did not describe the newer ship, room, telemetry and competency architecture.
- v0.14 demo and stress outputs existed, but reproducible v0.14 builder scripts were absent.
- Package verification checked listed files but did not reject unexpected unmanaged files.
- No single machine-readable local handoff, migration policy or builder capability-gap contract existed.

## Repairs

- Rewrote the three root handoff documents around the current checkpoint.
- Restored the ship-interior and rooted-crew visual pages and patched their builders.
- Added reproducible v0.14 demo and stress scripts.
- Added a strict handoff doctor with JSON, syntax, path, entrypoint, domain, bytecode, absolute-path and manifest checks.
- Added a no-silent-rewrite migration engine and policy.
- Added machine and human handoff manifests.
- Added builder capability-gap declaration schema and example.
- Added a prioritized future-potential backlog.
- Added a single offline handoff console.

## Deliberate non-change

The final polish does not invent missing spacecraft performance, guarantee long-duration stability or claim the future ideas already exist.


## Independent package recheck repairs

- Direct module commands assumed an editable install or manually configured `PYTHONPATH`; platform-safe wrappers now handle this.
- Running tests before the original handoff audit could create transient bytecode and cause a false failure; packaged bytecode is now distinguished from local runtime cache.
- The aggregate demo builder originally deleted unrelated handoff outputs, failed to recreate the bridge directory, and could remove later HTML entrypoints. Demo scopes are isolated and canonical entry templates are restored.
- Generated summaries used container-specific paths; they are now package-relative.
- Some truthful demo records include creation timestamps and are replay-valid rather than byte-identical. Canonical files and generated-output snapshots now have separate integrity manifests, refreshed automatically after a rebuild.
