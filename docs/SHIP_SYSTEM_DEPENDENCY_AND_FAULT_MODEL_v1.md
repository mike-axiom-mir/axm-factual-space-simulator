# Ship System Dependency and Fault Model v1

## Interface graph

The blueprint records electrical, thermal, mechanical, fluid, signal, software, human-procedure, and environmental interfaces.

Faults propagate through these interfaces rather than applying arbitrary hit-point loss.

```text
solar-array degradation
→ reduced generation
→ battery discharge
→ load shedding
→ reduced science and robotics
→ possible life-support reserve threat
```

```text
radiator loss
→ heat rejection deficit
→ thermal storage rise
→ power-load reduction
→ instrument and propulsion restrictions
```

```text
navigation sensor disagreement
→ larger uncertainty
→ high-consequence maneuvers held
→ command recall
→ additional sensing or reversible posture
```

## Fault management

The registry uses a living FMECA-style structure:

- failure mode;
- affected system;
- detection signals;
- effects;
- automatic reversible response;
- command authority level.

Command-required faults hold irreversible branches. Automation may isolate, shed loads, stop burns, enter shelter, preserve pressure, or enter a safe state. It may not invent a successful repair.
