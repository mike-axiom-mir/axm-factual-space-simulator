# AXM Action Report — v0.3.0 Four Command Modes

## Requested direction

Create four modes using one deterministic crew:

1. fully deterministic autonomous exploration;
2. AI command;
3. human command;
4. human + AI collaborative command with voting and discussion on disagreement.

## Built

- Four named and numbered command modes.
- Shared five-seat deterministic crew assessment.
- Reproducible crew votes and tie handling.
- State-aware risk, cost, curiosity, mission, and information-saturation scoring.
- Multi-turn autonomous deterministic execution.
- Forced deterministic outcome entropy in Mode 1.
- Explicit AI and human proposal records.
- Crew advice without silent command substitution.
- One-human/one-AI collaborative voting.
- Pending disagreement sessions with no automatic tie-break.
- Hash-chained human/AI discussion messages.
- Matching final votes required before execution.
- Preserved and archived collaboration transcripts.
- Command hashes embedded inside the event entropy context and event integrity chain.
- Separate command ledger and visual command console.
- Four working demonstration campaigns.

## Verification

- 28 automated tests pass.
- All four modes execute through the CLI.
- Autonomous mode completed an eight-turn reproducible command run.
- Autonomous action saturation caused the crew to vary observation, spectroscopy, and probe actions rather than repeat one safe choice indefinitely.
- Collaborative disagreement created a pending session without advancing the turn.
- Two discussion messages were stored and archived.
- Matching final votes resolved the collaborative command.
- Each demonstration event ledger replayed successfully.
- Tampering with command authority invalidates replay verification.

## Not claimed

- No bundled LLM is connected yet.
- Crew seats are not full conversational agents yet.
- The action set does not yet regenerate from every newly opened causal thread.
- Browser pages do not directly write authoritative local ledgers.
- This remains a scientifically constrained adventure foundation, not a complete astrophysics simulator or finished game.
