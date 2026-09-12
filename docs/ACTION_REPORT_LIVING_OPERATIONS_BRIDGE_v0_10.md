# Living Operations Bridge v0.10 — Post-Clearance Recovery

Status: **candidate / NON-CANON**

## Scope

v0.10 closes the semantic gap between verified fault clearance and a return from ship `safe_state`.

The v0.8 clearance engine deliberately records `safe_state_exit_automatic: false`. v0.10 preserves that boundary and adds a separate deterministic recovery path rather than treating fault removal as full restoration.

## Added

- `post_clearance_recovery.py`
  - static recovery contract/catalog for the Living Operations Bridge
  - verified clearance-receipt validation
  - residual-state assessment bound to the current authoritative ship-state hash
  - active multi-fault scan with blocking treatment for unknown, crew-survival, and command-required faults
  - explicit recovery evidence and independent-check gate
  - mission-commander safe-state-exit authorization receipt
  - semantic replay of assessment + authorization
  - atomic safe-state exit that changes control mode only
  - deterministic apply receipt and state-history entry
- Candidate policy JSON under `data/`.
- v0.10 renderer extension that visualizes:
  - `FAULT CLEARED`
  - `RECOVERY INCOMPLETE`
  - `DEGRADED SAFE / NOMINAL`
  - `RECOVERY VERIFIED`
  while keeping the renderer mutation-locked.
- Adversarial tests for stale-state replay, commander bypass, forged recovery status, authorization substitution, missing evidence, surviving command faults, deterministic receipt output, and residual-state preservation.

## Truth boundaries

Safe-state exit does **not**:

- restore battery energy, water, oxygen, crew availability, structure, or any other resource;
- restore system health or availability;
- remove existing load sheds;
- clear unrelated faults;
- clear pending command/irreversible-action holds;
- execute through the renderer;
- promote the candidate recovery authority policy to CANON.

A release is eligible only when the live ship state still semantically replays the assessment, crew-survival support is currently satisfied, blocking faults/holds are absent, recovery evidence is present, independent checks are present, and a mission commander explicitly authorizes exit.

If live safety evaluation would re-enter safe state, the exit transaction is rejected.

## Validation intent

The package reseal lane must regenerate and verify the deterministic package seal, run the full automated test suite, verify snapshots, and run the structural handoff audit before this candidate is treated as a trusted checkpoint. Normal cross-platform CI remains read-only.
