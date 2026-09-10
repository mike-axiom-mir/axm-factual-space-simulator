# Runtime Commit and Recovery v1

## Decision

`event_ledger.jsonl` is the canonical history of resolved adventure turns. Runtime state, command records, atlas visits, consoles, location packets and `manifest.json` are projections of a committed event plus its sealed atlas transition.

Resolving a turn now creates `.runtime_commit.json` before changing canonical history. The record uses schema `axm.runtime-commit.v1` and binds the prior event chain, new event, deterministically replayed state, command projection, pending command session and exact before/after atlas states under one SHA-256 seal.

## Commit order

1. Verify the prior ledger plus proposed event by deterministic replay.
2. Verify the supplied state is exactly the replayed state.
3. Verify the existing atlas visit chain and construct one append-only visit.
4. Atomically persist the sealed commit record.
5. Atomically replace the event ledger with its prior records plus the new event.
6. Rebuild the command ledger and write the runtime, council and atlas projections.
7. Rebuild consoles, packets and the output manifest.
8. Remove the commit record only after every projection is durable.

Single-file replacements write and sync a sibling temporary file before `os.replace`. Directory syncing is best-effort where the host filesystem does not expose it.

## Local single-writer contract

Every runtime initialization, command-mode change, pending council publication,
event commit and recovery first acquires the output directory's
`.runtime_mutation.lock`. The file is a stable coordination inode, not state or
evidence. Its contents have no authority. The operating system owns the actual
advisory lock and releases it when the process exits, including abrupt exit, so
there is no stale PID lease or mutable `latest` pointer to reclaim.

Admission is non-blocking. A second local process fails closed before it can
publish a commit journal or pending council state. Pending-state publication
also verifies that the caller's observed runtime state is still current while
holding the lock. The lock file must not be replaced or deleted while simulator
processes may be active; it is intentionally excluded from the output manifest.

## Restart contract

Every state-loading CLI path checks for a sealed commit first. `axm-star-sim recover-runtime --output <adventure>` also exposes recovery directly.

Recovery accepts exactly two ledger states: the sealed prior ledger, or that ledger with the sealed event already committed. It then idempotently finishes every projection. It fails closed and preserves the commit record if:

- the seal, schema, prior count or prior head is altered;
- deterministic event replay or the recorded target state disagrees;
- the event ledger contains any other history;
- the pending council session or archived resolution differs;
- the atlas differs from both sealed states, rewrites old visits, or does not append the committed event.

This is interruption recovery, not conflict merging. A divergent history requires explicit human inspection and a new branch; it is never overwritten automatically.

## Compatibility and boundary

Existing adventures need no migration because the lock file is noncanonical
and the sealed commit record appears only while a new event is being committed.
Event and runtime schemas are unchanged. The mechanism provides local
integrity, deterministic restart behavior and one admitted local runtime
mutator on the tested filesystem. It is not a distributed lock, signature,
author authentication or consensus protocol.
