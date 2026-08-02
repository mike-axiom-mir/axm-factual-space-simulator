# AXM Normalized Atlas Catalog Schema
## v0.7.0 intake boundary

The persistent atlas does not ingest a live catalogue directly into campaign history.

The safe path is:

```text
source release
→ immutable downloaded snapshot
→ source-specific normalization
→ axm.normalized-atlas-catalog.v1
→ validation
→ append-only catalog revision
→ explicit identity review across releases
```

## Required top-level fields

```json
{
  "schema": "axm.normalized-atlas-catalog.v1",
  "catalog_release_id": "provider-release-or-snapshot-id",
  "source_id": "registered_source_id",
  "snapshot_sha256": "64-lowercase-hex-characters",
  "downloaded_at": "ISO-8601 timestamp or null",
  "records": []
}
```

## Record shape

```json
{
  "release_scoped_record_id": "provider-record-id",
  "name": "human-readable object name",
  "aliases": ["optional alias"],
  "object_type": "star_or_system",
  "frame": "ICRS",
  "reference_epoch_jyear": 2016.0,
  "ra_deg": 217.42893801,
  "dec_deg": -62.67949575,
  "parallax_mas": 768.0665,
  "parallax_error_mas": 0.0499,
  "pmra_mas_per_year": -3781.741,
  "pmdec_mas_per_year": 769.465,
  "radial_velocity_km_s": null,
  "distance_product": null,
  "known_worlds": [],
  "field_provenance": {
    "astrometry": {
      "source_id": "registered_source_id",
      "release_scoped_record_id": "provider-record-id"
    }
  }
}
```

The numerical example only demonstrates structure. Production imports must preserve the exact source snapshot, release identity, units, nulls, uncertainties, and field-level provenance.

## Identity rule

`release_scoped_record_id` is not a permanent AXM location identity.

A new catalog release creates new candidate records. Cross-release matching must produce an explicit receipt using evidence such as:

- angular separation at a common epoch;
- proper-motion consistency;
- parallax and radial-velocity consistency;
- aliases and external cross-identifiers;
- uncertainty overlap;
- matcher version and review status.

Until that receipt exists, the importer does not silently merge two release-scoped records.

## Import command

```bash
python -m axm_star_sim atlas-import-catalog \
  --output output/my_campaign \
  --snapshot path/to/normalized_snapshot.json
```

The command adds a catalog revision. It does not mutate old visits or reinterpret old observations as new evidence.
