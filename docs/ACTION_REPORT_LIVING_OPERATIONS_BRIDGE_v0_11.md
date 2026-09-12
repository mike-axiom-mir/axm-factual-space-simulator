# Action Report — Living Operations Bridge v0.11

## Steward finding

v0.10 correctly separated verified fault clearance from full recovery and required an explicit commander-authorized safe-state exit. A remaining truth leak still existed in the low-level transition: safe-state exit produced `mode = "nominal"` even when the authoritative recovery assessment still contained residual damage, load sheds, degraded links, isolated rooms, or other bounded limitations.

That label could overstate the ship's condition. Leaving emergency safe state is not the same as returning to nominal operations.

## Implemented

### Truthful final operating mode

`src/axm_star_sim/operational_readiness.py` adds a final operational-release layer over the verified v0.10 recovery chain.

- residual indicators present → `degraded_operations`;
- no residual indicators → `nominal`;
- failed live safety evaluation → safe state remains enforced;
- the temporary v0.10 validation copy is never persisted as an intermediate nominal state;
- only operating mode, state history, and the state hash may change;
- resources, load sheds, crew state, system health, structure, active faults, and other residual state remain exactly as observed.

The transition returns a hashed `axm.operational-release-apply-receipt.v1` and supports deterministic full-chain replay.

### Read-only capability envelope

The authoritative released state can be converted into an `axm.operational-readiness-envelope.v1` covering:

- life-support monitoring;
- routine internal maintenance;
- science payload operations;
- robotics and probe operations;
- precision navigation maneuvers;
- docking and transfer;
- EVA and external operations;
- high-bandwidth communications;
- irreversible mission commitments.

Each operation is classified as `AVAILABLE`, `AVAILABLE_WITH_LIMITS`, or `HOLD`, with explicit blockers, limits, and evidence basis. The envelope cannot execute an operation or override a hold.

Candidate numeric thresholds are clearly labelled as simulation policy, not real-vehicle certification.

### Low-pixel bridge surface

The bridge now presents:

`SAFE STATE RELEASED → RESIDUAL CHECK → DEGRADED OPERATIONS / NOMINAL → CAPABILITY ENVELOPE`

It explicitly states:

- **NOMINAL IS NOT A DEFAULT**;
- residual state requires degraded-operations truth;
- the renderer cannot classify mode, apply release, execute operations, override holds, or claim nominal while residuals remain.

## Candidate policy

Policy ID:

`axm.operational-readiness-authority-policy.candidate.v1`

Truth status:

`simulation_policy_candidate_not_canon`

No CANON promotion, merge, release, or direct-main write is included in this run.

## Verification gate

The branch must pass:

- deterministic package reseal and recheck;
- canonical and generated snapshot verification;
- the complete automated test suite on Ubuntu and Windows;
- structural handoff audit;
- deterministic degraded and nominal release replay;
- tamper, stale-state, forged-mode, residual-mutation, and renderer-authority refusal checks.

## Remaining holds

- Visual review of the v0.11 panel on desktop and mobile remains required.
- Candidate readiness thresholds require governance review before promotion.
- The PR remains draft and unmerged.
