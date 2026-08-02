# AXM Persistent Expedition Atlas
## Architecture v0.7.0

Status: WORKING / TESTED FOUNDATION

## Purpose

The crew needs one map that remembers where it has been for the lifetime of the project.

The atlas must support two goals at once:

1. begin with as much real astronomical structure as the available catalog data supports;
2. continue into generated frontier space without presenting generated locations as discovered reality.

The map is therefore not one flat truth layer.

It keeps three distinct layers:

- **catalog space** — source-pinned astronomical locations and known system facts;
- **expedition space** — replayable crew visits, measurements, decisions, and consequences;
- **frontier space** — generated locations with explicit simulation-prior labels.

## Source foundation

The starter atlas uses:

- ESA Gaia DR3 / Gaia-derived astrometry for positions, parallaxes, and proper motions;
- SIMBAD as an object and cross-catalogue resolver with field-level bibliography/catalogue provenance;
- NASA Exoplanet Archive and NASA Science exoplanet records for known planetary systems;
- JPL Horizons and NAIF SPICE as the future authoritative route for Solar System body geometry and ephemerides.

Gaia DR3 uses reference epoch 2016.0 and ICRS-aligned positions. The starter records currently preserve their published source epoch rather than silently rewriting them to the campaign date.

The atlas includes a small pinned starter set:

- Solar System;
- Proxima Centauri;
- TRAPPIST-1;
- 51 Pegasi.

This is not intended to be the final map. It proves the schema and update path before larger Gaia and Exoplanet Archive snapshots are imported.

## Knowledge classes

### catalog_anchor

A real source-pinned astronomical location.

A catalog anchor may still contain unknowns. Knowing a position does not mean knowing every planet, moon, atmosphere, hazard, or resource.

### catalog_incomplete

A real source with insufficient information for a full simulation.

The simulator may preserve the coordinate while generating only clearly labelled hypotheses or priors around missing properties.

### procedural_frontier

A deterministic generated location used by the simulation.

It has a stable coordinate and can be revisited, but the coordinate is not evidence that a real uncatalogued system exists there.

### expedition_observation

A replayable fact inside the simulated expedition.

It is grounded in the ship state, instrument model, action, entropy receipt, and event hash.

### render_reconstruction

A later visual interpretation of preserved history.

It may look far better than the original interface, but it cannot become new evidence.

## Coordinate model

Catalog anchors preserve:

- coordinate frame;
- source epoch;
- right ascension and declination;
- parallax and uncertainty;
- proper motion and uncertainty where available;
- field-level source IDs.

For the map display, the atlas derives heliocentric Cartesian light-year coordinates.

The formula is:

```text
x = distance × cos(dec) × cos(ra)
y = distance × cos(dec) × sin(ra)
z = distance × sin(dec)
```

For the three nearby demonstration stars, distance is derived through simple parallax inversion because their relative parallax errors are small.

This is not a general distance-estimation method. Larger imports must preserve more appropriate distance products and uncertainty models.

The linear proper-motion display is also explicitly non-navigational. Precision Solar System navigation must use JPL Horizons or SPICE snapshots. Future interstellar navigation would require much more than a projected star catalogue.

## Persistent visit chain

Every visit records:

- location ID;
- visit type;
- event ID and event hash when applicable;
- state-after hash;
- action and outcome;
- authoritative location snapshot hash;
- previous visit hash;
- current visit hash.

Wall-clock time is excluded from the causal visit hash, while still being retained in the full record.

Changing an old outcome, location, or chain link invalidates verification.

## Catalog updates

New source releases do not rewrite old visits.

The update path is:

```text
new catalog snapshot
→ immutable snapshot hash
→ identity-resolution receipts
→ catalog revision
→ optional new current-location interpretation
→ old visit hashes remain unchanged
```

This matters because Gaia source identifiers are unique inside a release but are not guaranteed to identify the same astronomical source across different releases.

Cross-release identity must therefore use spatial neighbourhood, motion, aliases, and explicit review rather than blind identifier equality.

## Revisit and visual-engine growth

A revisit packet contains:

- authoritative location snapshot hash;
- relevant visit hashes;
- relevant event hashes;
- source-pinned coordinates and known worlds;
- crew observations;
- requested visual and asset-engine versions;
- a strict rule that rendering may not change history.

This creates the long-term path Mike described:

```text
2026 expedition
→ preserved low-graphics state and event ledger
→ later visual engine improves
→ revisit packet is generated
→ same location and history are reconstructed at higher fidelity
```

A more convincing landscape, cockpit, planet, or atmospheric effect does not make a speculative detail factual.

## Travel options versus feasibility

The atlas can expose an old location as a destination without claiming the current ship can reach it.

Each location separately stores:

- historical revisit availability;
- current physical-return status;
- route record;
- ship and propulsion feasibility status.

A map selection is an intention, not propulsion.

## Current honest limits

- The starter real catalog contains only four landmark systems.
- Full Gaia TAP ingestion is registered but not yet implemented in this version.
- Cross-release source identity resolution has a receipt schema but not an automated probabilistic matcher.
- Linear proper-motion propagation is for display only.
- The map currently uses a simple two-dimensional projection of three-dimensional positions.
- Procedural frontier coordinates do not model a complete Milky Way density distribution yet.
- Physical interstellar travel remains outside current human capability and must never be implied by the presence of a route line.

## Foundational rule

**The crew may improve its map, and the project may improve its visuals, but neither may silently improve the past.**
