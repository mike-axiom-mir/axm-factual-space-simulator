# AXM Factual Star Adventure Simulator
## Action Report v0.7.0 — Persistent Expedition Atlas

### Completed

- Added a persistent expedition-atlas schema.
- Added source-pinned starter landmarks for the Solar System, Proxima Centauri, TRAPPIST-1, and 51 Pegasi.
- Added ICRS-to-Cartesian atlas projection.
- Added display-only proper-motion propagation with explicit limits.
- Added deterministic procedural-frontier coordinates with simulation-prior labels.
- Added append-only, hash-chained visit records.
- Added crew observation attachment to visited locations.
- Added multi-system atlas import and route records.
- Added revisit options for old visited locations.
- Added visual-engine reconstruction packets that preserve authoritative location and event hashes.
- Added catalog revisions that cannot rewrite historical visits.
- Added an interactive local atlas HTML view.
- Added CLI commands: `atlas-status`, `atlas-import-system`, `revisit-location`, and `atlas-import-catalog`.

### Repair made during development

The first test pass used positional arguments against the keyword-only runtime event resolver. This failed immediately and was corrected. No test result was counted until the corrected suite passed.

### Honest limits

- Starter real catalogue is intentionally small.
- Added a normalized append-only catalog importer; full source-specific Gaia and Exoplanet Archive bulk download/normalization jobs remain future work.
- Cross-release identity matching is policy-complete but not automated.
- Proper-motion propagation is display-only.
- Route lines do not claim current or future flight feasibility.
- The frontier distribution is deterministic and three-dimensional, but not yet calibrated to a full Galactic population model.
