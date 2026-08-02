# Verification Report — v0.13.0

## Automated suite

- Tests passed: **171**
- New factual ship-blueprint tests: **28**
- Result: **PASS**

## Blueprint integrity

- Systems: **22**
- Physical modules: **5**
- Typed cross-system interfaces: **39**
- Registered FMECA-style failure modes: **20**
- Crew role qualification profiles: **7**
- Blueprint validation failures: **0**
- Source-reference validation failures: **0**

## Truth audit

Parameters in the integrated ship blueprint:

- Source-pinned catalog facts: **7**
- Disclosed simulation design assumptions: **39**
- Explicit unknowns: **10**

Important unknowns remain null, including complete integrated mass, verified delta-v, propulsion thrust, specific impulse, propellant load, structural acceleration rating, and guaranteed mission duration.

## Stress verification

- Independent deterministic ship states: **260**
- Multi-channel encounter packets: **260**
- Injected spacecraft failures: **260**
- Crew role-perspective snapshots: **1,820**
- Command recalls generated: **227**
- Nominal end states: **234**
- Safe-state end states: **26**
- Integrity failures: **0**
- Result: **PASS**

## Save-slot integration

New adventure slots pin:

- bridge archetype and version;
- interior archetype and version;
- crew start and version;
- ship blueprint and version;
- ship blueprint commitment;
- initial renderer and version.

Both regenerated demonstration slots verify their ship-start pins and remain playable offline.

## Artifact validation

- JSON artifacts parsed: **129**
- HTML artifacts checked: **40**
- Embedded JSON and JavaScript valid: **true**
- Package manifest and SHA-256 checks: performed after final packaging
- Clean extraction and complete test replay: performed after final packaging

## Honest engineering boundary

This package is a simulation-grade system architecture, not a flight-certified spacecraft design. It does not contain structural finite-element analysis, pressure-vessel certification, detailed fluid-network sizing, selected component part numbers, verified mass properties, full communications link budgets, propulsion throttle maps, medical radiation-dose prediction, or hardware qualification evidence.

Encounter effects are coupled to ship systems, but damage never proves hostile intent. Future conflict remains effects-first: detection, geometry, maneuver, power, thermal load, communications, sensors, pressure, structure, crew consequences, repair, and survival.
