# Astronomy Atlas Research Notes — v0.7.0

## Gaia DR3

ESA states that Gaia DR3 is based on observations collected from July 2014 to May 2017, uses reference epoch 2016.0, and reports positions and proper motions in ICRS. The Gaia archive provides positions, parallaxes, proper motions, radial velocities, photometry, and other source products.

Important identity rule: Gaia documentation warns that `source_id` is release-scoped and that the same astronomical source is not guaranteed to keep the same ID between releases. AXM therefore treats catalogue updates as revisions with identity-resolution receipts.

Sources:

- https://www.cosmos.esa.int/web/gaia/dr3
- https://gea.esac.esa.int/archive/documentation/GDR3/
- https://gea.esac.esa.int/archive/documentation/GEDR3/Gaia_archive/chap_datamodel/sec_dm_main_tables/ssec_dm_gaia_source.html

## NASA Exoplanet Archive

The NASA Exoplanet Archive provides TAP access to Planetary Systems and Planetary Systems Composite Parameters, including names, coordinates, host-star information, and planetary parameters.

AXM's long-term importer should preserve both:

- `ps` rows when a self-consistent literature solution matters;
- `pscomppars` when one-row-per-planet completeness is useful, with its consistency warnings preserved.

Sources:

- https://exoplanetarchive.ipac.caltech.edu/docs/TAP/usingTAP.html
- https://exoplanetarchive.ipac.caltech.edu/docs/intro.html

## JPL Horizons and SPICE

JPL Horizons provides programmatic ephemeris access and warns users to verify coordinate systems, timescales, and output quantities. AXM should use Horizons or SPICE for real Solar System location and orientation packets instead of treating a static atlas coordinate as sufficient.

Sources:

- https://ssd.jpl.nasa.gov/horizons/manual.html
- https://naif.jpl.nasa.gov/naif/

## SIMBAD starter landmarks

SIMBAD records were used to pin starter coordinates, parallax, and proper motion for:

- Proxima Centauri;
- TRAPPIST-1;
- 51 Pegasi.

These records cite Gaia DR3 astrometry. SIMBAD is used as an object resolver and provenance surface, not as permission to erase the underlying catalogue or bibliography reference.

Source:

- https://simbad.cds.unistra.fr/simbad/

## NASA starter planet facts

Small demonstration fact packets were pinned for:

- Proxima Centauri b;
- TRAPPIST-1 c;
- TRAPPIST-1 f;
- 51 Pegasi b.

Sources:

- https://science.nasa.gov/exoplanet-catalog/proxima-centauri-b/
- https://science.nasa.gov/exoplanet-catalog/trappist-1-c/
- https://science.nasa.gov/exoplanet-catalog/trappist-1-f/
- https://science.nasa.gov/exoplanet-catalog/51-pegasi-b/

## Research conclusion

The correct simulation structure is not “generate a galaxy and call it real.”

It is:

```text
catalogued astronomical skeleton
+ source uncertainty
+ known-system facts
+ simulation priors for missing detail
+ explicit procedural frontier
+ append-only crew exploration history
```
