# Verification Report — AXM Factual Star Adventure Simulator v0.4.0

## Status

**PASS for physics-coupled runtime, causal-thread action growth, command/replay integration, strict external-beacon rejection, and package-level source integrity.**

**BLS execution qualification:** the full quicknet verifier path is implemented, but its two pinned npm dependencies could not be downloaded in the isolated build container. The report therefore does not claim a live BLS pairing execution there.

## Automated unit/integration tests

```text
44 tests passed
```

Coverage includes:

- deterministic system generation;
- truth/source/formula validation;
- four command modes and collaborative discussion;
- deterministic and live entropy replay;
- physics preview completeness;
- orbital phase and flux evolution;
- expected versus realized measurement separation;
- probe launch and in-flight thread creation;
- impossible probe filtering;
- dynamic action-menu regeneration;
- no-empty-menu mission continuation;
- physics tamper detection;
- command/event/state hash-chain verification;
- drand packet structure, chain identity, signature/randomness hash relation, tamper rejection, verifier-unavailable handling, subprocess contract, and strict entropy refusal.

## Stress run

```text
300 generated systems
12 turns per system
3,600 events replay-verified
40 independently repeated deterministic campaign pairs
10 turns per repeated campaign
```

Observed action categories:

```text
engineering           694
general              1032
instrument            804
move_on               137
patient_observation   795
probe                  138
```

Observed outcome classes:

```text
ambiguous-evidence          856
clear-evidence             1111
operational-complication    948
quiet-constraint            282
unexpected-coupling         403
```

Thirteen thread kinds appeared. Menu size remained between 3 and 9 after the empty-menu repair.

The machine-readable report is `docs/stress_report_v0_4_0.json`.

## Demo verification

The included physics-thread demo contains five resolved deterministic events, including a probe launch and follow-up threads. All five replay checks passed for:

- event hash;
- record hash;
- outcome;
- rolls;
- probabilities;
- command;
- physics;
- action menu;
- final state hash.

## Browser/script checks

- `tools/drand_verifier/verify.mjs` passed `node --check`.
- Three generated JavaScript blocks passed `node --check`.
- The embedded system JSON block parsed successfully.

## drand fixture result in build container

Official round-42 fixture:

```text
structural valid: true
randomness == SHA-256(signature): true
packet material hash: true
BLS attempted: false
status: verifier_unavailable
```

This is intentional fail-closed behaviour. The packet is not accepted as entropy until local installation makes the BLS result true.

## Remaining limits

- Orbital and transfer models are two-body reference models, not N-body mission design.
- Thermal behavior is lumped and mostly steady-state.
- Radiation is a relative operations index, not dose or particle transport.
- Sensor parameters are representative and transparent, not calibrated hardware.
- Communication uses simplified vacuum light time and fixed link rate.
- AI Command still accepts a structured external AI decision rather than bundling an LLM.
- Browser consoles visualize/export state; Python remains authoritative for the ledger.
