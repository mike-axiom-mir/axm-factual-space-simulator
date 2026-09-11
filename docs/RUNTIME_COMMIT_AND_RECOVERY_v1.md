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
event commit, recovery and atlas-only read-modify-write transaction first
acquires the output directory's `.runtime_mutation.lock`. The file is a stable
coordination inode, not state or evidence. Its contents have no authority. The
operating system owns the actual advisory lock and releases it when the process
exits, including abrupt exit, so there is no stale PID lease or mutable `latest`
pointer to reclaim.

Admission is non-blocking. A second local process fails closed before it can
publish a commit journal, pending council state or atlas mutation. Pending-state
publication also verifies that the caller's observed runtime state is still
current while holding the lock. The lock file must not be replaced or deleted
while simulator processes may be active; it is intentionally excluded from the
output manifest.

Atlas-only commands acquire the same lock before reading the current atlas. If
a sealed runtime commit survived an interruption, they recover that exact
commit first; they then verify the visit chain before applying any catalog,
system-import or revisit change. The lock remains held through atlas, packet and
manifest publication, so the observation used by the mutation cannot become
stale through a cooperating local writer.

## Atlas-only commit contract

Atlas-only commands seal `.atlas_mutation_commit.json` before publishing any
changed projection. Schema `axm.atlas-mutation-commit.v1` binds the exact
before/after atlas states and, for a historical revisit, its exact packet. The
atlas remains the persistent source for atlas-only state; `atlas.html`,
`location_packet.json` and `manifest.json` are reconstructable projections. A
revisit packet is preserved evidence and must either be absent or exactly match
the sealed packet before recovery continues.

Publication writes the optional revisit packet, rebuilds all atlas projections,
rebuilds the manifest, and removes the commit only after those writes complete.
`axm-star-sim recover-atlas --output <adventure>` finishes this process without
creating a new catalog revision, visit, or render request. A following admitted
atlas or runtime mutation also finishes a surviving atlas commit before reading
or extending its state.

## Restart contract

Every state-loading CLI path checks for a sealed commit first. `axm-star-sim recover-runtime --output <adventure>` also exposes recovery directly.

Atlas-only recovery accepts exactly the sealed before or after atlas and refuses
to replace a divergent atlas or revisit packet. It also rejects a changed map
identity, invalid visit chain, rewritten visit prefix, unsafe packet identity,
packet/atlas linkage mismatch, altered schema, or altered seal. The journal is
preserved on every refusal for explicit inspection.

Recovery accepts exactly two ledger states: the sealed prior ledger, or that ledger with the sealed event already committed. It then idempotently finishes every projection. It fails closed and preserves the commit record if:

- the seal, schema, prior count or prior head is altered;
- deterministic event replay or the recorded target state disagrees;
- the event ledger contains any other history;
- the pending council session or archived resolution differs;
- the atlas differs from both sealed states, rewrites old visits, or does not append the committed event.

This is interruption recovery, not conflict merging. A divergent history requires explicit human inspection and a new branch; it is never overwritten automatically.

## Compatibility and boundary

Existing adventures need no migration because lock and commit files are
noncanonical and a sealed commit record appears only while a mutation is being
published.
Event and runtime schemas are unchanged. The mechanism provides local
integrity, deterministic restart behavior and one admitted local runtime
mutator on the tested filesystem. It is not a distributed lock, signature,
author authentication or consensus protocol.
