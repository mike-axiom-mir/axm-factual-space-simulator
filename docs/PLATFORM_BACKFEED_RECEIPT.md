# Platform backfeed receipt

## Outcome

The factual-space branch now emits a deterministic, dependency-free capsule for
generic capabilities that can return to the Workshop foundation without
bringing the simulator's identity, world state, data, story, or rendering lane.

Final capsule manifest SHA-256:

`a3410bcdc02f109826ddc70c9c82dee67167bcffea11bb7d7109528d47061c05`

The capsule declares three `EXPERIMENTAL` modules and 15 managed files:

1. `deterministic-json-core`
2. `immutable-history-guard`
3. `branch-backfeed-lab`

All three declare zero external dependencies and zero permissions. The capsule
policy refuses automatic install, registry mutation, promotion, and CANON
change.

## Evidence

- Deterministic rebuild: two independent temporary builds had identical trees.
- Tamper behavior: a same-length changed file produced `HOLD` with a SHA-256 mismatch.
- Contract structure: all three generated manifests/contracts passed the Workshop's existing `axm.module-contract/v1` verifier.
- JavaScript runtime: each module's Node self-test passed independently.
- Install behavior: a temporary Workshop received three new leaf modules, emitted a receiver receipt, changed the next plan digest, and refused replay of the old digest.
- Browser baseline: the local receiver rendered at 1280 x 720 with the picker, explicit integrity boundary, waiting state, and disabled export.
- Browser action: selecting the generated `dist` folder produced `READY_FOR_GRAFT`, 15/15 checked files, no failures, an enabled export button, and no warning/error console entries.
- Post-observation correction: HOLD now emits `hub:error`; only `READY_FOR_GRAFT` emits `hub:verify:pass`. The final deterministic tests cover that corrected source/build. The rendered layout was not changed by this correction.

## Shared-workspace boundary

`C:\axm workshop` was read only as the preserved architectural reference.
`D:\AXM_ACTIVE\workshop` was not modified. Two bounded read-only D checks timed
out under current vault I/O saturation, including the digest-producing install
plan. Therefore active-Workshop installation remains `UNKNOWN`, not claimed.

When D is responsive, run:

```text
run_platform_backfeed_install_plan.bat D:\AXM_ACTIVE\workshop
run_platform_backfeed_install_apply.bat <reviewed-plan-digest> D:\AXM_ACTIVE\workshop
```

Apply refuses an existing target and changes only new `tools/<module-id>/` leaf
directories plus an install receipt under `state/branch-backfeed/receipts/`.
Registry wiring, live Workshop verification, Graft review, and promotion remain
separate gates.
