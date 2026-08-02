# Research foundation — 2026-08-02

## Architecture decision

The simulator separates five truth layers:

1. **Catalog fact** — imported from a named, pinned source snapshot.
2. **Derived** — calculated from declared inputs using a registered formula.
3. **Simulation prior** — generated input used to construct a plausible fictional system.
4. **Observation** — information the in-game instruments have actually produced.
5. **Hypothesis / speculation** — possible explanations that cannot become fact without evidence.

This separation is required because the NASA Exoplanet Archive itself distinguishes literature values and calculated values, and warns that the one-row-per-planet PSCompPars table can combine parameters from multiple references and is not necessarily internally self-consistent. The future high-integrity route is therefore:

- use `ps` when a self-consistent published solution is required;
- use `pscomppars` for population calibration and broad completeness;
- pin every download as a snapshot;
- never blend imported and generated values without labels.

## Primary registered sources

### IAU nominal constants

IAU 2015 Resolution B3 supplies nominal solar and planetary conversion constants. These are used as exact conversion factors inside the simulator, not treated as live measurements.

### NASA Exoplanet Archive

The TAP service exposes `ps`, `pscomppars`, stellar-host and other tables. Version 0.1 includes a standard-library TAP downloader for PSCompPars. Future versions should add:

- schema discovery;
- PS reference-level ingestion;
- catalog uncertainty propagation;
- source DOI and bibcode capture;
- empirical distribution calibration;
- atmospheric-spectroscopy joins.

### JPL Solar System Dynamics

The JPL SBDB adapter is included for asteroids and comets. Horizons is registered for later ephemerides, state vectors and visual trajectory validation.

### NASA NAIF SPICE

SPICE is the future precision-real-system mode. It should remain optional because it has a learning and deployment cost. It is appropriate for real bodies, spacecraft geometry, frames, time systems and mission kernels—not for every fictional system.

### NASA Planetary Data System

PDS is a long-term, peer-reviewed planetary mission archive. It should feed future surface, atmosphere, plasma, rings, geology and instrument-response modules through node-specific adapters rather than one giant importer.

### ESA Gaia + IVOA TAP

Gaia provides stellar astrometry and population data. IVOA TAP/ADQL provides the interoperability layer for many astronomical services, so the long-term updater should be registry-driven rather than hardcoded to one archive.

## Physics included now

- Stefan-Boltzmann stellar luminosity;
- Kepler two-body period approximation;
- NASA Exoplanet Archive equilibrium-temperature relation;
- NASA Exoplanet Archive incident-flux relation;
- bulk density/mass conversion;
- surface gravity;
- escape velocity.

## Physics deliberately not faked yet

- N-body stability;
- tidal heating;
- stellar evolution tracks;
- atmospheric chemistry;
- magnetospheres;
- greenhouse climate;
- biological emergence;
- relativistic travel;
- calibrated instrument noise;
- real SPICE frame transformations;
- detailed planet formation.

Adventure text may point toward these as hypotheses, but the engine must not claim to have simulated them until corresponding modules exist.

## Factual-generator growth rule

New knowledge enters through:

```text
source registry
→ adapter
→ immutable raw snapshot
→ normalized records
→ validation
→ calibration package
→ generator version
→ new campaign
```

It does not enter by editing old campaign JSON.
