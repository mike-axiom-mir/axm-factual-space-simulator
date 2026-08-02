# Verification Report — AXM Factual Star Adventure Simulator v0.3.0

## Result

**PASS for the declared v0.3 command-mode scope.**

## Automated tests

Command:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Result:

- 28 tests passed;
- 0 failures;
- 0 errors.

Covered areas include:

- exactly four registered command modes;
- deterministic crew assessment reproducibility;
- autonomous command ownership;
- AI command preservation;
- human command preservation;
- matching collaborative votes;
- disagreement without automatic tie-break;
- discussion message chaining;
- matching final-vote requirement;
- command authority inside event replay integrity;
- command-console and pending-session output;
- reproducible autonomous story sequence;
- autonomous action diversification through information saturation;
- existing generator, source, truth-layer, entropy, and ledger tests.

## Autonomous stress test

- 200 generated star systems;
- 10 autonomous deterministic turns per system;
- 2,000 command/event resolutions;
- every event replay-verified immediately;
- 12 distinct generated action texts exercised;
- no impossible autonomous probe command occurred;
- no replay failure occurred.

## Independent deterministic-run comparison

Two separately generated campaigns used the same seed and ran 10 autonomous turns.

Result:

- action sequence matched;
- outcome sequence matched;
- causal event hashes matched;
- three different actions appeared in the sequence.

Wall-clock timestamps remain in the audit record, but are intentionally excluded from the causal event hash. A separate record hash protects the complete timestamped record.

## Four-mode demonstrations

`output/four_modes_demo/` contains:

- `mode_1_autonomous` — eight deterministic autonomous turns;
- `mode_2_ai_command` — AI-selected probe action with crew advice;
- `mode_3_human_command` — human-selected spectroscopy action with crew advice;
- `mode_4_collaboration` — initial disagreement, two discussion messages, matching final votes, and resolved event.

All four demonstration event ledgers passed replay verification.

The collaborative session was archived under `command_sessions/` and its full transcript was embedded in the resolved command record.

## Browser artifact checks

- 12 executable JavaScript blocks extracted from the generated system, command, and adventure consoles;
- all 12 passed `node --check`;
- embedded `application/json` payload blocks were validated indirectly by generation and Python JSON loading and were correctly excluded from JavaScript syntax checks.

## Integrity behavior

The runtime records:

- command hash;
- command authority and mode;
- crew assessment;
- proposals and rationales;
- optional discussion transcript and transcript hash;
- event causal hash;
- full record hash;
- resulting state hash;
- previous causal event hash.

Changing recorded command authority causes verification failure.

## Honest limits

The verification does not claim:

- a bundled live AI model;
- full conversational crew agents;
- dynamically regenerated action menus after every causal thread;
- research-grade N-body, climate, biology, or spacecraft simulation;
- browser authority to append directly to local ledgers.
