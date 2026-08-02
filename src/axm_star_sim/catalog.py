from __future__ import annotations

import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

NASA_FIELD_MAP = {
    "pl_orbper": ("orbital_period", "days"),
    "pl_orbsmax": ("semi_major_axis", "AU"),
    "pl_rade": ("radius", "earth_radius"),
    "pl_bmasse": ("mass", "earth_mass"),
    "pl_dens": ("density", "g/cm3"),
    "pl_eqt": ("equilibrium_temperature", "K"),
    "pl_insol": ("insolation", "earth_flux"),
    "pl_orbeccen": ("eccentricity", None),
    "st_teff": ("stellar_effective_temperature", "K"),
    "st_rad": ("stellar_radius", "solar_radius"),
    "st_mass": ("stellar_mass", "solar_mass"),
    "st_lum": ("stellar_log_luminosity", "dex_solar"),
    "st_met": ("stellar_metallicity", "dex"),
    "sy_dist": ("system_distance", "pc"),
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def build_nasa_exoplanet_archive_url(limit: int = 500) -> str:
    import urllib.parse

    if limit < 1 or limit > 100_000:
        raise ValueError("limit must be between 1 and 100000")
    columns = [
        "pl_name", "hostname", "disc_year", "discoverymethod", "pl_orbper", "pl_orbsmax",
        "pl_rade", "pl_bmasse", "pl_dens", "pl_eqt", "pl_insol", "pl_orbeccen",
        "st_teff", "st_rad", "st_mass", "st_lum", "st_met", "sy_dist",
    ]
    query = f"select top {int(limit)} {','.join(columns)} from pscomppars where pl_name is not null order by disc_year desc"
    return "https://exoplanetarchive.ipac.caltech.edu/TAP/sync?" + urllib.parse.urlencode(
        {"query": query, "format": "json"}
    )


def build_jpl_sbdb_url(query: str) -> str:
    import urllib.parse

    query = query.strip()
    if not query:
        raise ValueError("JPL SBDB query cannot be empty")
    return "https://ssd-api.jpl.nasa.gov/sbdb.api?" + urllib.parse.urlencode(
        {"sstr": query, "phys-par": "1", "full-prec": "1"}
    )


def normalize_nasa_snapshot(snapshot_dir: Path, output_path: Path) -> dict[str, Any]:
    manifest_path = snapshot_dir / "manifest.json"
    raw_path = snapshot_dir / "raw.json"
    normalized_source_path = snapshot_dir / "normalized.json"
    if not manifest_path.exists() or not raw_path.exists():
        raise FileNotFoundError("snapshot requires manifest.json and raw.json")

    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows_path = normalized_source_path if normalized_source_path.exists() else raw_path
    rows = json.loads(rows_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("NASA Exoplanet Archive snapshot must contain a JSON list")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    missing_names = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = row.get("pl_name")
            if not name:
                missing_names += 1
                continue
            facts: dict[str, Any] = {}
            for original, (canonical, unit) in NASA_FIELD_MAP.items():
                value = row.get(original)
                if value is None:
                    continue
                facts[canonical] = {
                    "value": value,
                    "unit": unit,
                    "truth_type": "catalog_fact",
                    "source_ids": ["nasa_exoplanet_archive_pscomppars"],
                    "formula_id": None,
                    "uncertainty": None,
                    "notes": "Imported from a pinned PSCompPars snapshot. Parameters may originate from different references and are not guaranteed to form one self-consistent literature solution.",
                }
            record = {
                "schema": "axm.catalog-record.v1",
                "record_type": "exoplanet",
                "object_id": str(name),
                "host_name": row.get("hostname"),
                "discovery_year": row.get("disc_year"),
                "discovery_method": row.get("discoverymethod"),
                "source_id": "nasa_exoplanet_archive_pscomppars",
                "source_snapshot_sha256": source_manifest.get("sha256") or _sha256_file(raw_path),
                "source_retrieved_at": source_manifest.get("retrieved_at"),
                "facts": facts,
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1

    result = {
        "schema": "axm.normalization-manifest.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_id": "nasa_exoplanet_archive_pscomppars",
        "source_snapshot": str(snapshot_dir),
        "source_snapshot_sha256": source_manifest.get("sha256") or _sha256_file(raw_path),
        "output": str(output_path),
        "output_sha256": _sha256_file(output_path),
        "records": count,
        "skipped_missing_name": missing_names,
    }
    output_path.with_suffix(output_path.suffix + ".manifest.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def _records(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at line {number}: {exc}") from exc
            if isinstance(value, dict):
                yield value


def summarize_catalog(input_path: Path, output_path: Path) -> dict[str, Any]:
    values: dict[str, list[float]] = {canonical: [] for canonical, _ in NASA_FIELD_MAP.values()}
    total = 0
    methods: dict[str, int] = {}
    for record in _records(input_path):
        total += 1
        method = record.get("discovery_method") or "unknown"
        methods[str(method)] = methods.get(str(method), 0) + 1
        for name, evidence in record.get("facts", {}).items():
            if name not in values:
                continue
            value = evidence.get("value")
            if isinstance(value, (int, float)):
                values[name].append(float(value))

    fields: dict[str, Any] = {}
    for name, collected in values.items():
        if not collected:
            fields[name] = {"available": 0, "missing_fraction": 1.0 if total else None}
            continue
        ordered = sorted(collected)
        fields[name] = {
            "available": len(collected),
            "missing_fraction": round(1 - len(collected) / total, 6) if total else None,
            "minimum": ordered[0],
            "median": statistics.median(ordered),
            "maximum": ordered[-1],
        }

    report = {
        "schema": "axm.catalog-summary.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": str(input_path),
        "input_sha256": _sha256_file(input_path),
        "records": total,
        "discovery_methods": dict(sorted(methods.items(), key=lambda item: (-item[1], item[0]))),
        "fields": fields,
        "truth_type": "catalog_summary",
        "automatic_generator_authority": False,
        "warnings": [
            "This describes the downloaded observed catalog, not the true underlying universe population.",
            "Detection methods produce strong selection effects and missing-data patterns.",
            "The report may inform reviewed priors, but it must not silently replace them.",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
