# Offline-First Adventure Save Slots — v0.9.0

## Root decision

AI-forged starting scenarios are optional. The simulator must remain fully usable by a human, a machine, or both without an external AI connection.

## Start choices

### Offline base — default

The local runtime performs seven independent deterministic constraint passes. Each pass evaluates scientifically bounded anomaly and agnostic-life candidates. The passes vote on an investigation lens, and the local forge seals the hidden starting state before play.

This mode needs:

- Python;
- the bundled registries;
- the generated world seed;
- no network;
- no model;
- no API key;
- no service account.

### External AI assisted — optional

A human or external AI receives a safe request containing:

- public system conditions;
- a locally validated candidate shortlist;
- observable channels;
- false-positive control depth;
- claim ceilings.

The external seat may propose investigation emphasis. It may not directly choose:

- whether life exists;
- whether aliens appear;
- the hidden origin class;
- a guaranteed outcome;
- the evidence stage ceiling;
- the resolution secret.

The proposal is imported once. The local runtime validates it, chooses only within its constrained shortlist, seals the hidden state, publishes a commitment, and disconnects the external dependency.

## Save-slot structure

```text
slot/
├── SLOT_METADATA.json
├── SLOT_MANIFEST.json
├── SLOT_HANDOFF.txt
├── slot_console.html
├── slot_private/
│   └── START_RECEIPT.json
├── session/
│   ├── forge_private/
│   ├── player_public/
│   └── BLIND_FORGE_HANDOFF.txt
└── exports/
    └── *_BLIND_PLAYER_BUNDLE.zip
```

`slot_private` and `session/forge_private` remain host-only during blind play.

## Continuity

After creation, both modes use the same local event resolver, evidence ladder, entropy receipts, state files, and replay verification. The external model is never needed again.

## Integrity

Each slot maintains a SHA-256 manifest. Verification checks:

- every managed file;
- the private pre-play commitment;
- the public/private separation;
- every event against its stored private entropy token;
- final public state against replay;
- save metadata against the verified state.

A future UI may replace the command line without changing this storage contract.
