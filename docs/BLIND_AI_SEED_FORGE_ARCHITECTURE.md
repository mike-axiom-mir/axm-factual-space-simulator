# Blind AI Seed Forge Architecture — v0.8.0

## Core correction

A single AI must not both know the hidden scenario and role-play surprise.

The architecture now separates:

1. **Forge AI** — creates a private, source-bounded starting phenomenon before play.
2. **Validator** — checks theory authority, environmental eligibility, false-positive controls, and claim ceilings.
3. **Explorer AI or human** — receives only public world facts, actions, observations, and evidence state.
4. **Host/oracle** — resolves actions against the sealed private packet without exposing it.
5. **Post-play verifier** — reveals and verifies the private packet when the chosen reveal condition is reached.

## What is fixed before play

The forge packet can fix:

- a theory/anomaly test lens;
- a hidden simulation-origin class;
- hidden physical or chemical traits;
- false-positive mechanisms;
- eligible observations and controls;
- a resolution secret;
- a source and reasoning scorecard.

This is **private simulation truth**, not a real-world scientific claim.

## What remains open

The forge does not predetermine the full story. These remain dependent on play and runtime state:

- which action the explorer chooses;
- viewing geometry and instrument family;
- which measurements cross detection thresholds;
- runtime entropy and noise realization;
- ship resources and mission time;
- whether controls explain a candidate;
- whether evidence advances, stalls, or collapses;
- whether the expedition leaves without resolution.

## Filesystem blindness

A blind session is written as:

```text
session/
├── forge_private/
│   ├── hidden_scenario.json
│   └── ENTROPY_TOKENS.json
├── player_public/
│   ├── system_public.json
│   ├── mission_bundle.json
│   ├── player_state.json
│   ├── event_ledger.jsonl
│   └── player_console.html
└── BLIND_FORGE_HANDOFF.txt
```

Only `player_public/` is given to the exploring AI or human.

## Pre-play commitment

Before play, the complete private packet is canonically serialized and committed through a domain-separated SHA-256 hash.

The public bundle contains the commitment, but not the packet.

After play, the private packet can be revealed and hashed again. If any hidden trait, selected theory pair, false-positive mechanism, or resolution secret was altered, the commitment fails.

## Event verification

Each event records:

- action;
- public state-before hash;
- entropy-token hash;
- observed channel and threshold;
- evidence stage after the action;
- prior event hash;
- public event hash;
- sealed resolution receipt.

After reveal, the verifier can replay every event with the preserved entropy tokens. This separates legitimate hidden-state play from after-the-fact story rewriting.

## Evidence restraint

A single result can advance the evidence ladder by no more than one stage. Higher stages require:

- multiple tested channels;
- independent confirmation;
- false-positive controls;
- convergent evidence;
- compatibility with the hidden scenario's scientific ceiling.

Even a hidden candidate living system cannot instantly become confirmed external biology.

## AI proposal contract

A future model may replace the built-in reference forge by emitting a structured proposal containing:

- selected registry IDs;
- explicit environment constraints;
- observable channels;
- falsification tests;
- false-positive candidates;
- claim ceiling;
- source IDs;
- concise scorecard and rationale.

The validator may reject the proposal. The model never receives permission to invent a new fact type or remove uncertainty labels.
