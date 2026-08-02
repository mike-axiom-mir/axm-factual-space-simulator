# Open Future Architecture — v0.2.0

## The repaired seed rule

Version 0.1 made the initial star system and selected opportunity reproducible. That is useful, but a fully deterministic campaign also means a sufficiently informed machine could calculate the entire future before anyone plays.

Version 0.2 separates three things:

1. **Initial reality** — stable star, planets, ship, opportunity and source versions.
2. **Decision context** — the action chosen, current resources, previous event hash and available evidence.
3. **Resolution entropy** — sampled only when the event is actually resolved.

The new core rule is:

> The seed defines the starting universe and its possibility space. It does not have to define every event that will ever happen.

## Deferred resolution

An event context is not created until the crew chooses an action. It includes:

- system ID;
- current turn;
- selected opportunity;
- exact action;
- state-before hash;
- probability snapshot;
- previous event hash.

Only after this context exists does the chosen entropy mode resolve the outcome.

This prevents the system from secretly storing a complete branch tree and pretending it emerged later.

## Five resolution modes

### 1. Deterministic

The event result is derived from the master seed and exact event context.

Use it for:

- tests;
- debugging;
- cross-runtime verification;
- exact replays.

It is intentionally labelled `predetermined_by_master_seed: true`.

### 2. Local live

Fresh bytes are requested from the operating system at the moment of resolution through Python's `secrets` module.

Use it for:

- solo local adventures;
- human + AI shared expeditions;
- offline sessions where the future should not be calculable from the original seed.

The entropy token is written to the event ledger afterward. This means the event becomes replayable once it has happened without implying that it existed before resolution.

### 3. Mixed live

The campaign's deterministic identity is mixed with fresh local entropy.

This is the default recommended AXM mode because it keeps the event tied to:

- this universe;
- this state;
- this action;
- this moment of resolution.

Yet the exact result is not derivable from the master seed alone.

### 4. External beacon

A preserved pulse from a public randomness provider is mixed with the event context.

The starter includes a drand Quicknet fetch adapter. It preserves:

- provider;
- round;
- randomness value;
- signature;
- previous signature when provided;
- source URL;
- retrieval time.

The current Python starter preserves verification material but does **not** implement full BLS signature verification. It says so in every fetched packet.

For fair multiplayer use, the crew should commit to a future round before that round is published. Fetching several already-known rounds and choosing the nicest one would not be fair.

### 5. Party commit–reveal

Each human or machine seat creates a hidden value and a public commitment hash.

Flow:

1. every seat creates its public commitment;
2. all public commitments are exchanged or locked;
3. every seat reveals its value and salt;
4. AXM verifies that each reveal matches its earlier commitment;
5. all verified contributions are combined with the event context.

No single honest participant can predict the combined value before the other hidden values are revealed.

Honesty limit: a participant can still refuse to reveal after seeing the others. This v0.2 starter detects invalid reveals but does not solve abort fairness.

## Event ledger

Every resolved event records:

- action;
- probability snapshot before the roll;
- entropy source and replay material;
- outcome and secondary detail rolls;
- observation versus hypothesis labels;
- resource changes;
- newly opened causal thread;
- prior event hash;
- event hash;
- state-after hash.

`verify-ledger` reconstructs each outcome from the recorded entropy and checks the entire chain.

## No fake novelty claim

This system does not claim that an outcome has never been imagined by any human or AI.

It can honestly claim that:

- the exact event was conditioned on the generated universe, current state and chosen action;
- live modes added entropy not contained in the master seed;
- the result was not written to the event ledger before resolution;
- the causal and entropy trail can be inspected afterward.

## Browser console versus Python authority

`adventure_console.html` demonstrates live action resolution directly in a browser using Web Crypto when available. It can export its browser ledger.

The Python runtime remains authoritative for serious campaigns because it persists:

- runtime state;
- append-only JSONL event ledger;
- event hashes;
- state hashes;
- replay verification.
