# Source-Pinned Technology Core Architecture

## Root rule

The seed selects the technology. AXM does not select a favorite technology, adjust weights, or fill missing specifications.

```text
master seed
→ named branch: ship/technology-core
→ SHA-256 digest
→ modulo equal sorted eligible catalog slots
→ selected source-pinned lineage
→ known parameters + explicit unknowns
→ bounded scenario physics
```

## Four eligible 2027 lineages

1. `blue_moon_mk2_pathfinder_2027`
2. `gateway_ppe_halo`
3. `orion_esm_crew_transport`
4. `spacex_starship_hls_pathfinder_2027`

Every lineage occupies one equal catalog slot. There are no technology weights.

## Truth layers

### Catalog fact

A published parameter copied into the registry with one or more source IDs and a unit.

### Derived

Transparent arithmetic over catalog values with a registered formula. Example: Orion maximum standalone person-days = crew capacity × mission duration.

### Source-bounded potential scenario

A simulation value constrained by a catalog fact but not claimed as flight configuration. Example: an AXM action may allocate a labelled fraction of published total generation to a reference instrument. This does not claim that payload power is actually available after platform loads.

### Unbounded reference scenario

A transparent experiment used where the exact core lacks a published value. It is never presented as installed hardware or demonstrated capability.

### Blocked unknown

A calculation that cannot be performed honestly from the pinned registry. Typical blocked quantities include acceleration, delta-v capability, crew g-load, range, payload, and propellant endurance.

## Technology physics envelope

Every pre-entropy physics snapshot now contains:

- selected core identity and seed-selection receipt;
- catalog date and planning horizon;
- published generation, crew, and duration values when available;
- a labelled power-scenario status;
- propulsion capability labels without invented performance;
- radiation/protection capability labels without invented shielding factors;
- the exploration-fiction functions supported only as partial analogs;
- unknown parameters and blocked calculations;
- an explicit authority rule.

## Requirement versus capability

AXM may calculate an environmental requirement independently of the ship:

- orbital geometry;
- light-time delay;
- stellar flux;
- a reference transfer time and delta-v requirement.

That does not establish that the selected technology core can execute the maneuver. Execution capability requires sufficient published mass, thrust, specific impulse, propellant, thermal, structural, and guidance data.

## Update path

```text
new official source
→ immutable snapshot or reviewed record
→ source registry entry
→ technology registry patch
→ validation
→ new registry version
→ new campaigns may use it
→ old campaigns retain their pinned registry version
```

A status update can make a core ineligible without altering prior campaign evidence.
