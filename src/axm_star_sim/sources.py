from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .catalog import build_jpl_sbdb_url, build_nasa_exoplanet_archive_url


def _retrieve_json(url: str, timeout: int = 60) -> tuple[bytes, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "AXM-Factual-Star-Simulator/0.4"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    return raw, json.loads(raw.decode("utf-8"))


def _write_snapshot(output: Path, source_id: str, request_url: str, raw: bytes, parsed: Any) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha256(raw).hexdigest()
    directory = output / f"{source_id}_{stamp}_{digest[:10]}"
    directory.mkdir()
    (directory / "raw.json").write_bytes(raw)
    manifest = {
        "source_id": source_id,
        "retrieved_at": now.isoformat(),
        "request_url": request_url,
        "sha256": digest,
        "bytes": len(raw),
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (directory / "normalized.json").write_text(json.dumps(parsed, indent=2), encoding="utf-8")
    return directory


def update_nasa_exoplanet_archive(output: Path, limit: int = 500) -> Path:
    url = build_nasa_exoplanet_archive_url(limit)
    raw, parsed = _retrieve_json(url)
    return _write_snapshot(output, "nasa_exoplanet_archive", url, raw, parsed)


def update_jpl_sbdb(output: Path, query: str) -> Path:
    url = build_jpl_sbdb_url(query)
    raw, parsed = _retrieve_json(url)
    return _write_snapshot(output, "jpl_sbdb", url, raw, parsed)
