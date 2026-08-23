# AXM Living Operations Bridge v0.8 — Authoritative Verified Fault Clearance

Status: **DRAFT CANDIDATE / HOLD FOR MERGE GATE**

## Steward finding before build

The repository already had the authoritative half of this problem. `ship_blueprint.py` owns an `axm.ship-state.v1` with per-system `active_fault_ids`, a hash-chained `fault_ledger`, hash-chained state history, safe-state evaluation, a final `state_hash`, `apply_failure_mode()`, and `verify_ship_state()`.

v0.7 already produced an evidence-bounded `axm.fault-clearance-candidate.v1`, but deliberately stopped before state mutation.

The missing seam was therefore not another fault registry or another repair model. It was the **symmetric, verified authoritative clearance transition** back into the existing ship-state engine.

## Added

### `src/axm_star_sim/fault_clearance_apply.py`

Adds an authoritative apply function that accepts only a verified effective v0.7 repair attempt and its clearance candidate.

Before mutation it verifies:

- current `axm.ship-state.v1` integrity through existing `verify_ship_state()`;
- v0.7 candidate hash and clearance-eligibility boundary;
- repair-attempt receipt chain and deterministic attempt identity;
- pinned v0.5 procedure-definition hash;
- candidate / attempt / procedure / failure-registry / system identity agreement;
- target fault is currently active in authoritative `system_health`;
- no prior application of the same clearance candidate;
- an explicit clearance authorization receipt;
- an exact state reconciliation receipt pinned to the current `state_hash`.

### No inverse repair arithmetic

`apply_failure_mode()` changes several different state paths depending on the failure. v0.8 does **not** reverse those effects mathematically and does not restore a remembered baseline.

Instead, each failure-effect key maps only to the state paths that require external post-repair reconciliation. Every required path must provide:

- exact `expected_current_value`;
- evidence-backed `verified_value`;
- one or more evidence IDs.

The full supplied path set must equal the required path set. Extra state mutations are refused. Stale current-value preconditions are refused. Unknown failure-effect mappings are refused rather than guessed.

This permits persistent consequences to remain persistent. A repaired pressure leak does not automatically restore lost gas; a repaired battery fault does not automatically create energy; repaired structural damage is not automatically assigned health 1.0. The verified state receipt decides only what observations actually support.

### Authority candidate

The existing crew-role registry contains maintenance-work-order and command/irreversible-branch authority, but no explicit `fault_clearance` verb. v0.8 therefore does **not** silently widen an existing role.

It introduces the explicitly non-canonical candidate policy:

`axm.fault-clearance-authority-policy.candidate.v1`

- advisory failure: primary procedure role must authorize;
- command-required failure: mission commander + primary procedure role must authorize;
- if the primary role is itself mission commander, that single role satisfies both groups.

Truth label: `simulation_policy_candidate_not_canon`.

### Atomic apply behavior

On a valid application v0.8:

1. deep-copies the authoritative state;
2. applies only the evidence-covered reconciliation paths;
3. removes only the target failure ID from the target system;
4. refuses a `nominal` source-system mode if another active fault remains there;
5. clears a matching command recall only when no other command-required fault needs it; otherwise deterministically retargets the recall;
6. appends a `verified_clearance` lifecycle record through the existing hash-chained fault-ledger primitive;
7. reevaluates safe-state entry without automatically exiting safe state;
8. appends existing hash-chained state history;
9. recomputes the ship state hash;
10. runs existing `verify_ship_state()` against the result;
11. returns a hashed `axm.fault-clearance-apply-receipt.v1`.

## Bridge integration

The low-pixel bridge gets a presentation-only **Authoritative Fault Clearance** panel. It shows that the final engine exists and the inputs it requires, but the browser remains locked:

- no ship-state mutation;
- no repair execution;
- no fault clearance;
- no inferred restored values.

The final v0.7 ladder stage now has an explicit v0.8 engine boundary rather than a vague future placeholder.

## Verification before GitHub publication

Detached focused suite:

- 11 focused checks: **PASS**;
- 1 real-repository authoritative roundtrip test: intentionally deferred until repository CI because detached staging does not contain the full ship registries;
- Python syntax: PASS;
- v0.8 JavaScript syntax: PASS.

The repository integration test performs the actual lifecycle with real registries:

`create_ship_state → apply_failure_mode → complete procedure → topology → repair gate → external execution receipt → effective independent verification → clearance candidate → exact reconciliation → authoritative clearance apply → verify_ship_state`.

## Honest holds

- Candidate authority policy is not CANON.
- No claim that any physical repair method is validated by this engine.
- No automatic merge, release, CANON promotion, or safe-state exit.
- Existing `verify_ship_state().fault_count` historically counts fault-ledger records; v0.8 adds lifecycle clearance records to that ledger, so active-fault truth should continue to come from `system_health[*].active_fault_ids` / compact active-fault count rather than treating ledger length as active faults.
- Visual desktop/mobile review remains separate from deterministic engine verification.
