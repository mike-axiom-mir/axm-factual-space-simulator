# Physics-Coupled Outcomes and Causal-Thread Growth

## Purpose

Version 0.4 replaces generic outcome wording as the authoritative runtime driver. The simulator now calculates a complete expected physical snapshot before entropy is drawn, then uses entropy only to resolve uncertainty around that expectation.

The central order is:

```text
current universe + ship state + selected action
→ expected physics snapshot
→ physics-adjusted outcome probabilities
→ declared entropy source
→ realized noisy measurement
→ observation and provisional interpretation
→ resource/state change
→ opened or updated causal threads
→ regenerated action menu
```

This ordering is included in the event hash chain.

## 1. Orbital phase

The runtime advances each target with a two-body Keplerian model:

```text
M(t) = M0 + 2πt/P
E - e sin(E) = M
r = a(1 - e cos(E))
```

The generated orbital period, eccentricity, phase, and mission clock therefore affect star distance, illuminated fraction, stellar flux, thermal input, sensor contrast, and communication geometry.

Limit: no N-body perturbations, precession, relativity, resonances, or numerical ephemeris integration.

## 2. Sensor expectation and realized measurement

The expected detector state records signal electrons and each major noise term separately:

```text
variance = signal + background + dark + read variance + systematic variance
expected SNR = signal / sqrt(variance)
```

After the entropy packet is resolved, the runtime produces a separately stored realized SNR and detail channel. The expected value is never overwritten by the random measurement.

Limit: this is a representative transparent detector model at a fixed reference wavelength. It is not a calibrated NASA instrument or a replacement for an observatory simulator.

## 3. Thermal load

The ship uses a lumped radiative balance:

```text
absorbed stellar power
+ instrument waste heat
+ inherited ship heat
- radiator emission
= net thermal power
```

Action parameters can alter integration time, instrument power, incidence attitude, or cooldown time. The outcome probabilities then respond to the thermal-load ratio rather than using a generic danger roll.

Limit: no transient thermal-node network, conduction topology, finite-element geometry, phase changes, or material aging.

## 4. Radiation environment

Version 0.4 uses a bounded relative operations/electronics risk index driven by stellar-age activity, inverse-square distance, and a declared shielding factor.

It is explicitly **not**:

- absorbed dose;
- particle transport;
- a single-event-effect prediction;
- a biological or medical exposure estimate.

The index exists to make close approaches and shielding choices causally relevant while preserving the line between simulation and radiation engineering.

## 5. Communication delay

The runtime stores:

- one-way light time;
- round-trip light time;
- data volume;
- link rate;
- transmission duration;
- earliest possible full response.

A probe or distant crew cannot provide immediate feedback when the physical light-time says otherwise.

Limit: simplified vacuum propagation and fixed link rate; no antenna gain, pointing loss, occultation, coding, weather, relay scheduling, or network contention.

## 6. Probe trajectory

A two-impulse Hohmann transfer provides a transparent reference time and delta-v between the ship orbit and target orbit. Launched probes remain in the runtime state with launch time, expected arrival time, trajectory, and communications state.

Limit: no optimized launch window, plane change, finite burn, gravity assist, perturbation, low-thrust optimization, or collision avoidance.

## 7. Dynamic causal threads

Events may open or update:

- `precision-follow-up`;
- `competing-hypotheses`;
- `cross-system-coupling`;
- `repair-versus-discovery`;
- `detection-limit-review`;
- `probe-in-flight`;
- `communication-latency`;
- `radiation-watch`;
- `thermal-recovery`.

Each thread retains parentage, source event, target body, evidence, visits, status, depth, and update turn. The next menu is generated from active threads and ship conditions.

A long expedition can resolve every current investigation. Version 0.4 then creates an explicit three-choice mission-continuation menu: evidence review, new system survey, or maintenance. It does not return an empty bridge or silently reopen a closed thread.

## Integrity rule

Replay verifies:

- exact selected action record;
- action-menu hash;
- expected physics hash;
- probability snapshot;
- entropy packet and rolls;
- outcome and realized measurement;
- resource changes;
- causal-thread changes;
- next action menu;
- final state hash.

Changing the recorded physics or causal menu makes replay fail.
