# Four Command Modes Architecture

## Shared foundation

All modes use the same deterministic crew assessment. This prevents each mode from secretly becoming a different simulation.

Crew seats:

1. Science — prioritizes evidence and discovery.
2. Navigation — prioritizes safe and efficient trajectories.
3. Engineering — protects power, instruments, heat, and hardware.
4. Hazard Watch — gives danger the strongest weight.
5. Mission — balances purpose, progress, and scientific value.

Each action receives values for curiosity, safety, efficiency, mission value, effective risk, effective cost, repetition count, and information saturation. Every crew seat votes from its declared weights. The complete assessment is embedded in the command record.

## Mode 1: Deterministic Crew Expedition

Authority: deterministic crew.

The crew's vote and utility result selects the action. Repeated actions accumulate information saturation and a stagnation penalty, preventing a safe observation from remaining optimal forever. Ship damage, heat, fuel, probe availability, and sensor health can also change later choices.

Mode 1 always uses deterministic event entropy. Given the same version, generated universe, and event history, the action and outcome sequence is reproducible.

## Mode 2: AI Command

Authority: AI commander.

The AI submits an action and rationale. The crew still calculates its advice and warnings, but it cannot silently replace the selected valid action. The command record shows whether the AI followed or rejected the crew recommendation.

The AI integration boundary is intentionally simple: a local model, hosted model, scripted agent, or another machine can all emit the same proposal packet later.

## Mode 3: Human Command

Authority: human commander.

The human submits an action and rationale. The crew gives the same advice it would give an AI. Valid commands execute without hidden correction. Impossible commands, such as deploying a probe when none remain, are rejected by the runtime rather than story-written around.

## Mode 4: Human + AI Collaborative Command

Authority: human–AI council.

The command vote is intentionally symmetrical:

- human: one vote;
- AI: one vote.

Matching votes create a resolved command. Different votes create a pending council session containing both actions, both rationales, the crew assessment, and the exact state hash.

Discussion messages are hash-chained. Either participant can revise its proposed action while explaining why. The runtime executes only after both final votes match.

There is no automatic tie-break, hidden captain, random winner, or crew override. A later governance layer may add explicitly selected fallback rules, but v0.3 does not silently invent one.

## Integrity path

```text
system + current state
→ deterministic crew assessment
→ explicit authority mode
→ proposal(s)
→ optional discussion transcript
→ resolved command hash
→ deferred event entropy
→ outcome
→ event hash
→ state hash
```

Changing the recorded authority, action, command rationale, discussion transcript, probability snapshot, entropy receipt, outcome, or resulting state causes replay verification to fail.
