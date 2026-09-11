from __future__ import annotations

import copy
import hashlib
import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .registry import data_path, load_json, load_source_registry
from .seed import SeedBranch
from .storage import atomic_write_json, atomic_write_text

ATLAS_SCHEMA = "axm.expedition-atlas.v1"
LOCATION_SCHEMA = "axm.atlas-location.v1"
VISIT_SCHEMA = "axm.atlas-visit.v1"
REVISIT_SCHEMA = "axm.revisit-render-packet.v1"
CATALOG_REVISION_SCHEMA = "axm.atlas-catalog-revision.v1"


class AtlasError(ValueError):
    """Raised when the persistent expedition atlas contract is violated."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_hash(value: Any, domain: str = "AXM-EXPEDITION-ATLAS-V1") -> str:
    return hashlib.sha256((domain + "\n" + _canonical(value)).encode("utf-8")).hexdigest()


def load_atlas_policy() -> dict[str, Any]:
    return load_json(data_path("atlas_policy.json"))


def load_landmark_catalog() -> dict[str, Any]:
    return load_json(data_path("atlas_landmark_catalog.json"))


def validate_atlas_sources(catalog: dict[str, Any] | None = None) -> list[str]:
    catalog = catalog or load_landmark_catalog()
    policy = load_atlas_policy()
    required_policy = [
        "catalog_facts_and_simulation_frontier_are_never_merged_without_labels",
        "old_visits_are_append_only",
        "new_catalog_releases_create_revisions_not_rewrites",
        "new_visual_engines_create_reconstruction_packets_not_new_history",
        "route_availability_is_not_route_feasibility",
        "unknown_space_may_be_generated_but_must_remain_simulation_prior",
        "crew_observations_may_refine_a_location_but_may_not_rewrite_the_pinned_catalog_snapshot",
        "cross_release_identity_requires_provenance_and_spatial_matching",
    ]
    missing = [key for key in required_policy if policy.get("policy", {}).get(key) is not True]
    if missing:
        raise AtlasError(f"missing mandatory atlas policies: {missing}")
    known_sources = set(load_source_registry().get("sources", {}))
    ids: set[str] = set()
    for landmark in catalog.get("landmarks", []):
        location_id = str(landmark.get("location_id", ""))
        if not location_id or location_id in ids:
            raise AtlasError(f"duplicate or missing landmark ID: {location_id!r}")
        ids.add(location_id)
        if landmark.get("knowledge_class") != "catalog_anchor":
            raise AtlasError(f"starter landmark is not catalog_anchor: {location_id}")
        sources = set(landmark.get("source_ids", []))
        coordinates = landmark.get("coordinates", {})
        sources.update(coordinates.get("source_ids", []))
        distance = landmark.get("distance_ly", {})
        sources.update(distance.get("source_ids", []))
        for facts in landmark.get("world_facts", {}).values():
            sources.update(facts.get("source_ids", []))
        unknown = sources - known_sources
        if unknown:
            raise AtlasError(f"landmark {location_id} has unknown source IDs: {sorted(unknown)}")
    if "catalog:sol" not in ids:
        raise AtlasError("atlas landmark catalog must contain catalog:sol")
    return []


def icrs_cartesian_ly(ra_deg: float, dec_deg: float, distance_ly: float) -> dict[str, float]:
    ra = math.radians(float(ra_deg))
    dec = math.radians(float(dec_deg))
    distance = float(distance_ly)
    return {
        "x_ly": round(distance * math.cos(dec) * math.cos(ra), 9),
        "y_ly": round(distance * math.cos(dec) * math.sin(ra), 9),
        "z_ly": round(distance * math.sin(dec), 9),
    }


def propagate_icrs_linear(coordinates: dict[str, Any], target_epoch: float) -> dict[str, Any]:
    """Small-angle proper-motion propagation for map display, not precision navigation."""
    if coordinates.get("frame") != "ICRS":
        return copy.deepcopy(coordinates)
    source_epoch = 2000.0 if coordinates.get("epoch") == "J2000" else float(coordinates.get("epoch", 2000.0))
    years = float(target_epoch) - source_epoch
    dec_deg = float(coordinates["dec_deg"])
    cos_dec = max(1e-9, abs(math.cos(math.radians(dec_deg))))
    ra_delta_deg = float(coordinates.get("pmra_mas_yr", 0.0)) * years / (3_600_000.0 * cos_dec)
    dec_delta_deg = float(coordinates.get("pmdec_mas_yr", 0.0)) * years / 3_600_000.0
    result = copy.deepcopy(coordinates)
    result.update({
        "propagated_epoch": float(target_epoch),
        "propagated_ra_deg": round((float(coordinates["ra_deg"]) + ra_delta_deg) % 360.0, 10),
        "propagated_dec_deg": round(max(-90.0, min(90.0, dec_deg + dec_delta_deg)), 10),
        "propagation_model": "linear tangent-plane proper-motion approximation",
        "navigation_authority": "display_only",
        "warning": "No perspective acceleration, orbital multiplicity, covariance propagation, or full radial-motion solution is included.",
    })
    return result


def _landmark_location(record: dict[str, Any]) -> dict[str, Any]:
    location = copy.deepcopy(record)
    coordinates = location.get("coordinates", {})
    if coordinates.get("frame") == "ICRS":
        location["cartesian_ly"] = icrs_cartesian_ly(
            coordinates["ra_deg"], coordinates["dec_deg"], location["distance_ly"]["value"]
        )
        location["coordinates_2026_display"] = propagate_icrs_linear(coordinates, 2026.583)
    else:
        location["cartesian_ly"] = {
            "x_ly": float(coordinates.get("x_ly", 0.0)),
            "y_ly": float(coordinates.get("y_ly", 0.0)),
            "z_ly": float(coordinates.get("z_ly", 0.0)),
        }
    location.update({
        "schema": LOCATION_SCHEMA,
        "catalog_revision": 1,
        "visit_count": 0,
        "crew_observations": [],
        "render_history": [],
        "route_status": "mapped_not_proven_reachable",
        "route_feasibility": {
            "status": "unknown",
            "rule": "A mapped coordinate is not evidence that the selected spacecraft can reach it."
        },
    })
    location["authoritative_snapshot_sha256"] = canonical_hash(
        {k: v for k, v in location.items() if k not in {"authoritative_snapshot_sha256", "visit_count", "crew_observations", "render_history"}},
        "AXM-ATLAS-LOCATION-SNAPSHOT-V1",
    )
    return location


def _frontier_location(system: dict[str, Any]) -> dict[str, Any]:
    master_seed = str(system["master_seed"])
    rng = SeedBranch(master_seed, "atlas/location").rng()
    ra_deg = rng.uniform(0.0, 360.0)
    dec_deg = math.degrees(math.asin(rng.uniform(-1.0, 1.0)))
    distance_ly = rng.uniform(65.0, 1800.0)
    coordinates = {
        "frame": "ICRS-like simulation frame",
        "epoch": "campaign_origin",
        "ra_deg": round(ra_deg, 9),
        "dec_deg": round(dec_deg, 9),
        "distance_ly": round(distance_ly, 6),
        "truth_type": "simulation_prior",
        "source_ids": ["axm_simulation_priors_v1"],
        "warning": "This coordinate is a deterministic simulation anchor. It is not a claim that a catalogued system exists here."
    }
    location = {
        "schema": LOCATION_SCHEMA,
        "location_id": f"frontier:{system['system_id']}",
        "name": system["name"],
        "object_class": "generated_stellar_system",
        "knowledge_class": "procedural_frontier",
        "coordinates": coordinates,
        "cartesian_ly": icrs_cartesian_ly(ra_deg, dec_deg, distance_ly),
        "distance_ly": {
            "value": round(distance_ly, 6),
            "truth_type": "simulation_prior",
            "source_ids": ["axm_simulation_priors_v1"],
        },
        "known_worlds": [planet["name"] for planet in system.get("planets", [])],
        "source_ids": ["axm_simulation_priors_v1"],
        "system_id": system["system_id"],
        "system_state_sha256": canonical_hash(system, "AXM-ATLAS-SYSTEM-STATE-V1"),
        "catalog_revision": 0,
        "visit_count": 0,
        "crew_observations": [],
        "render_history": [],
        "route_status": "active_simulated_expedition",
        "route_feasibility": {
            "status": "simulation_contract",
            "rule": "Travel is resolved by the simulator's ship and mission physics. The coordinate alone grants no capability."
        },
    }
    location["authoritative_snapshot_sha256"] = canonical_hash(
        {k: v for k, v in location.items() if k not in {"authoritative_snapshot_sha256", "visit_count", "crew_observations", "render_history"}},
        "AXM-ATLAS-LOCATION-SNAPSHOT-V1",
    )
    return location


def build_expedition_atlas(system: dict[str, Any], created_at: str | None = None) -> dict[str, Any]:
    validate_atlas_sources()
    catalog = load_landmark_catalog()
    locations = {item["location_id"]: _landmark_location(item) for item in catalog["landmarks"]}
    frontier = _frontier_location(system)
    locations[frontier["location_id"]] = frontier
    now = created_at or datetime.now(timezone.utc).isoformat()
    atlas = {
        "schema": ATLAS_SCHEMA,
        "atlas_version": "0.7.0",
        "map_id": f"atlas-{hashlib.sha256(system['master_seed'].encode('utf-8')).hexdigest()[:16]}",
        "created_at": now,
        "updated_at": now,
        "active_location_id": frontier["location_id"],
        "origin_location_id": "catalog:sol",
        "coordinate_contract": {
            "catalog_frame": "ICRS with source epoch preserved",
            "display_frame": "heliocentric Cartesian light-years",
            "precision_rule": "Display propagation is never used as precision navigation. Solar-system navigation must use Horizons/SPICE snapshots.",
        },
        "catalog_snapshot": {
            "catalog_version": catalog["catalog_version"],
            "catalog_sha256": canonical_hash(catalog, "AXM-ATLAS-CATALOG-SNAPSHOT-V1"),
            "identity_warning": catalog["identity_warning"],
            "source_ids": sorted({source for item in catalog["landmarks"] for source in item.get("source_ids", [])}),
        },
        "locations": locations,
        "routes": [{
            "route_id": f"route:sol:{frontier['location_id']}",
            "from_location_id": "catalog:sol",
            "to_location_id": frontier["location_id"],
            "kind": "campaign_entry",
            "availability": "simulator_entry_route",
            "feasibility": "not_a_real_spaceflight_claim",
            "created_from": "master_seed + initial campaign state",
        }],
        "visits": [],
        "visit_chain_head": None,
        "catalog_revisions": [],
        "revisit_packets": [],
        "render_contract": load_atlas_policy()["revisit_contract"],
        "growth_contract": {
            "future_catalogs": "New source snapshots add revisions and identity-resolution receipts. They never overwrite old expedition evidence.",
            "future_visual_engines": "Old locations can be rendered again from immutable location and event hashes.",
            "frontier": "Generated locations remain procedural_frontier unless later catalog evidence independently matches them; even then the match requires explicit review.",
        },
    }
    atlas = record_visit(
        atlas,
        location_id="catalog:sol",
        event=None,
        visit_kind="expedition_origin",
        note="Crew atlas initialized at the Solar System origin.",
        visited_at=now,
    )
    atlas = record_visit(
        atlas,
        location_id=frontier["location_id"],
        event=None,
        visit_kind="campaign_arrival",
        note="Generated expedition location registered without claiming catalog existence.",
        visited_at=now,
    )
    return atlas


def register_system_location(atlas: dict[str, Any], system: dict[str, Any], make_active: bool = True) -> dict[str, Any]:
    updated = copy.deepcopy(atlas)
    location = _frontier_location(system)
    existing = updated["locations"].get(location["location_id"])
    if existing and existing.get("authoritative_snapshot_sha256") != location.get("authoritative_snapshot_sha256"):
        raise AtlasError("location ID collision with a different authoritative snapshot")
    updated["locations"][location["location_id"]] = existing or location
    if make_active:
        previous = updated.get("active_location_id")
        updated["active_location_id"] = location["location_id"]
        if previous and previous != location["location_id"]:
            updated["routes"].append({
                "route_id": f"route:{len(updated['routes']) + 1:06d}",
                "from_location_id": previous,
                "to_location_id": location["location_id"],
                "kind": "expedition_transition",
                "availability": "simulation_route_opened",
                "feasibility": "resolved_by_event_ledger_not_coordinate_map",
                "created_from": system["system_id"],
            })
    updated["updated_at"] = datetime.now(timezone.utc).isoformat()
    return updated


def record_visit(
    atlas: dict[str, Any],
    location_id: str,
    event: dict[str, Any] | None,
    visit_kind: str = "exploration_event",
    note: str | None = None,
    visited_at: str | None = None,
) -> dict[str, Any]:
    updated = copy.deepcopy(atlas)
    if location_id not in updated.get("locations", {}):
        raise AtlasError(f"unknown atlas location: {location_id}")
    location = updated["locations"][location_id]
    prior_hash = updated.get("visit_chain_head")
    visit_number = len(updated.get("visits", [])) + 1
    payload = {
        "schema": VISIT_SCHEMA,
        "visit_id": f"visit-{visit_number:08d}",
        "visit_number": visit_number,
        "visited_at": visited_at or datetime.now(timezone.utc).isoformat(),
        "location_id": location_id,
        "visit_kind": visit_kind,
        "note": note,
        "event_id": event.get("event_id") if event else None,
        "event_hash": event.get("event_hash") if event else None,
        "state_after_sha256": event.get("state_after_sha256") if event else None,
        "action": event.get("action") if event else None,
        "outcome": event.get("outcome", {}).get("title") if event else None,
        "authoritative_location_snapshot_sha256": location["authoritative_snapshot_sha256"],
        "previous_visit_hash": prior_hash,
    }
    causal = copy.deepcopy(payload)
    causal.pop("visited_at", None)
    payload["visit_hash"] = canonical_hash(causal, "AXM-ATLAS-VISIT-CHAIN-V1")
    updated.setdefault("visits", []).append(payload)
    updated["visit_chain_head"] = payload["visit_hash"]
    location["visit_count"] = int(location.get("visit_count", 0)) + 1
    if event:
        observation = {
            "event_id": event["event_id"],
            "event_hash": event["event_hash"],
            "turn": event["turn"],
            "action": event["action"],
            "outcome_id": event["outcome"]["id"],
            "outcome_title": event["outcome"]["title"],
            "truth_type": "expedition_observation",
            "measurement": copy.deepcopy(event["outcome"].get("measurement")),
        }
        location.setdefault("crew_observations", []).append(observation)
    updated["active_location_id"] = location_id
    updated["updated_at"] = payload["visited_at"]
    return updated


def verify_visit_chain(atlas: dict[str, Any]) -> dict[str, Any]:
    previous = None
    checks = []
    for visit in atlas.get("visits", []):
        causal = copy.deepcopy(visit)
        recorded = causal.pop("visit_hash", None)
        causal.pop("visited_at", None)
        expected = canonical_hash(causal, "AXM-ATLAS-VISIT-CHAIN-V1")
        valid = visit.get("previous_visit_hash") == previous and recorded == expected
        checks.append({"visit_id": visit.get("visit_id"), "valid": valid})
        if not valid:
            return {"valid": False, "checks": checks, "chain_head": previous}
        previous = recorded
    return {"valid": previous == atlas.get("visit_chain_head"), "checks": checks, "chain_head": previous}


def revisit_options(atlas: dict[str, Any]) -> list[dict[str, Any]]:
    options = []
    for location_id, location in atlas.get("locations", {}).items():
        if int(location.get("visit_count", 0)) < 1:
            continue
        options.append({
            "location_id": location_id,
            "name": location["name"],
            "knowledge_class": location["knowledge_class"],
            "visit_count": location["visit_count"],
            "observation_count": len(location.get("crew_observations", [])),
            "authoritative_snapshot_sha256": location["authoritative_snapshot_sha256"],
            "latest_render_engine": location.get("render_history", [])[-1]["visual_engine_version"] if location.get("render_history") else None,
            "travel_option_status": "historical_revisit_available",
            "physical_return_status": "must_be_resolved_by_current_ship_and_route_physics",
        })
    return sorted(options, key=lambda item: (-item["visit_count"], item["name"]))


def create_revisit_packet(
    atlas: dict[str, Any],
    location_id: str,
    visual_engine_version: str,
    asset_engine_version: str = "unversioned",
    camera_language: str = "crew-memory-reconstruction",
    created_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if location_id not in atlas.get("locations", {}):
        raise AtlasError(f"unknown atlas location: {location_id}")
    location = atlas["locations"][location_id]
    if int(location.get("visit_count", 0)) < 1:
        raise AtlasError("a location must have at least one recorded visit before historical reconstruction")
    relevant_visits = [v for v in atlas.get("visits", []) if v.get("location_id") == location_id]
    packet = {
        "schema": REVISIT_SCHEMA,
        "packet_id": f"revisit-{canonical_hash([atlas['map_id'], location_id, visual_engine_version, asset_engine_version], 'AXM-REVISIT-ID-V1')[:20]}",
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "map_id": atlas["map_id"],
        "location_id": location_id,
        "location_name": location["name"],
        "knowledge_class": location["knowledge_class"],
        "authoritative_location_snapshot_sha256": location["authoritative_snapshot_sha256"],
        "visit_chain_head": atlas.get("visit_chain_head"),
        "included_visit_hashes": [visit["visit_hash"] for visit in relevant_visits],
        "included_event_hashes": [visit["event_hash"] for visit in relevant_visits if visit.get("event_hash")],
        "catalog_revision": location.get("catalog_revision"),
        "coordinates": copy.deepcopy(location.get("coordinates")),
        "cartesian_ly": copy.deepcopy(location.get("cartesian_ly")),
        "known_worlds": copy.deepcopy(location.get("known_worlds", [])),
        "crew_observations": copy.deepcopy(location.get("crew_observations", [])),
        "render_request": {
            "visual_engine_version": visual_engine_version,
            "asset_engine_version": asset_engine_version,
            "camera_language": camera_language,
            "render_mode": "historical_reconstruction",
            "may_improve_visual_fidelity": True,
            "may_change_authoritative_history": False,
        },
        "honesty": {
            "new_render_is_not_new_evidence": True,
            "catalog_facts_remain_source_pinned": True,
            "simulation_frontier_remains_labelled": location["knowledge_class"] == "procedural_frontier",
        },
    }
    packet["packet_sha256"] = canonical_hash(
        {k: v for k, v in packet.items() if k not in {"created_at", "packet_sha256"}},
        "AXM-REVISIT-PACKET-V1",
    )
    updated = copy.deepcopy(atlas)
    history = {
        "packet_id": packet["packet_id"],
        "packet_sha256": packet["packet_sha256"],
        "visual_engine_version": visual_engine_version,
        "asset_engine_version": asset_engine_version,
        "created_at": packet["created_at"],
    }
    updated["locations"][location_id].setdefault("render_history", []).append(history)
    updated.setdefault("revisit_packets", []).append({"location_id": location_id, **history})
    updated["updated_at"] = packet["created_at"]
    return packet, updated



def import_normalized_catalog(atlas: dict[str, Any], snapshot: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Import a versioned normalized star/system catalog without auto-merging identities."""
    if snapshot.get("schema") != "axm.normalized-atlas-catalog.v1":
        raise AtlasError("normalized atlas snapshot must use schema axm.normalized-atlas-catalog.v1")
    snapshot_id = str(snapshot.get("snapshot_id", "")).strip()
    if not snapshot_id:
        raise AtlasError("normalized atlas snapshot requires snapshot_id")
    records = snapshot.get("records")
    if not isinstance(records, list):
        raise AtlasError("normalized atlas snapshot records must be a list")
    known_sources = set(load_source_registry().get("sources", {}))
    snapshot_sources = set(snapshot.get("source_ids", []))
    unknown_snapshot_sources = snapshot_sources - known_sources
    if unknown_snapshot_sources:
        raise AtlasError(f"normalized atlas snapshot has unknown sources: {sorted(unknown_snapshot_sources)}")

    updated = copy.deepcopy(atlas)
    imported = 0
    skipped_existing = 0
    identity_receipts: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        external_id = str(record.get("external_id", "")).strip()
        name = str(record.get("name", "")).strip()
        if not external_id or not name:
            raise AtlasError(f"catalog record {index} requires external_id and name")
        sources = set(record.get("source_ids", [])) | snapshot_sources
        unknown = sources - known_sources
        if unknown:
            raise AtlasError(f"catalog record {external_id} has unknown sources: {sorted(unknown)}")
        ra_deg = float(record["ra_deg"])
        dec_deg = float(record["dec_deg"])
        if not 0.0 <= ra_deg < 360.0 or not -90.0 <= dec_deg <= 90.0:
            raise AtlasError(f"catalog record {external_id} has invalid ICRS coordinates")
        if record.get("distance_ly") is not None:
            distance_ly = float(record["distance_ly"])
            distance_truth = "catalog_fact"
            formula_id = None
        elif record.get("parallax_mas") is not None and float(record["parallax_mas"]) > 0:
            distance_ly = 1000.0 / float(record["parallax_mas"]) * 3.261563777
            distance_truth = "derived"
            formula_id = "inverse_parallax_nearby_demo"
        else:
            raise AtlasError(f"catalog record {external_id} requires distance_ly or positive parallax_mas")
        location_id = f"catalog-import:{snapshot_id}:{external_id}"
        coordinates = {
            "frame": "ICRS",
            "epoch": record.get("epoch", snapshot.get("epoch", "source_epoch")),
            "ra_deg": ra_deg,
            "dec_deg": dec_deg,
            "parallax_mas": record.get("parallax_mas"),
            "parallax_error_mas": record.get("parallax_error_mas"),
            "pmra_mas_yr": record.get("pmra_mas_yr"),
            "pmdec_mas_yr": record.get("pmdec_mas_yr"),
            "truth_type": "catalog_fact",
            "source_ids": sorted(sources),
        }
        location = {
            "schema": LOCATION_SCHEMA,
            "location_id": location_id,
            "name": name,
            "object_class": record.get("object_class", "astronomical_source"),
            "knowledge_class": record.get("knowledge_class", "catalog_incomplete"),
            "coordinates": coordinates,
            "cartesian_ly": icrs_cartesian_ly(ra_deg, dec_deg, distance_ly),
            "distance_ly": {
                "value": round(distance_ly, 9),
                "truth_type": distance_truth,
                "formula_id": formula_id,
                "source_ids": sorted(sources),
            },
            "known_worlds": copy.deepcopy(record.get("known_worlds", [])),
            "source_ids": sorted(sources),
            "catalog_snapshot_id": snapshot_id,
            "external_id": external_id,
            "catalog_revision": 1,
            "visit_count": 0,
            "crew_observations": [],
            "render_history": [],
            "route_status": "mapped_not_proven_reachable",
            "route_feasibility": {
                "status": "unknown",
                "rule": "Imported coordinates do not imply current ship reachability.",
            },
        }
        location["authoritative_snapshot_sha256"] = canonical_hash(
            {k: v for k, v in location.items() if k not in {"authoritative_snapshot_sha256", "visit_count", "crew_observations", "render_history"}},
            "AXM-ATLAS-LOCATION-SNAPSHOT-V1",
        )
        if location_id in updated["locations"]:
            if updated["locations"][location_id]["authoritative_snapshot_sha256"] != location["authoritative_snapshot_sha256"]:
                raise AtlasError(f"catalog import collision for {location_id}; create a new snapshot_id")
            skipped_existing += 1
        else:
            updated["locations"][location_id] = location
            imported += 1
        identity_receipts.append({
            "location_id": location_id,
            "external_id": external_id,
            "identity_status": "release_scoped_record",
            "automatic_cross_release_merge": False,
            "review_rule": "Match future releases using position, motion, aliases, uncertainty, and explicit provenance.",
        })

    snapshot_hash = canonical_hash(snapshot, "AXM-NORMALIZED-ATLAS-CATALOG-V1")
    updated = append_catalog_revision(
        updated,
        source_snapshot_id=snapshot_id,
        source_snapshot_sha256=snapshot_hash,
        identity_receipts=identity_receipts,
    )
    report = {
        "schema": "axm.atlas-catalog-import-report.v1",
        "snapshot_id": snapshot_id,
        "snapshot_sha256": snapshot_hash,
        "records_received": len(records),
        "locations_imported": imported,
        "locations_already_present": skipped_existing,
        "automatic_cross_release_merges": 0,
        "identity_receipts": len(identity_receipts),
    }
    return updated, report

def append_catalog_revision(
    atlas: dict[str, Any],
    source_snapshot_id: str,
    source_snapshot_sha256: str,
    identity_receipts: list[dict[str, Any]],
    created_at: str | None = None,
) -> dict[str, Any]:
    updated = copy.deepcopy(atlas)
    revision = {
        "schema": CATALOG_REVISION_SCHEMA,
        "revision_number": len(updated.get("catalog_revisions", [])) + 1,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "source_snapshot_id": source_snapshot_id,
        "source_snapshot_sha256": source_snapshot_sha256,
        "identity_receipts": copy.deepcopy(identity_receipts),
        "historical_visits_rewritten": False,
        "rule": "New catalog information is attached as a revision. Existing location snapshots, visits, and event hashes remain unchanged.",
    }
    revision["revision_sha256"] = canonical_hash(
        {k: v for k, v in revision.items() if k not in {"created_at", "revision_sha256"}},
        "AXM-ATLAS-CATALOG-REVISION-V1",
    )
    updated.setdefault("catalog_revisions", []).append(revision)
    updated["updated_at"] = revision["created_at"]
    return updated


def write_atlas_files(output: Path, atlas: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output / "expedition_atlas.json", atlas)
    atomic_write_text(output / "atlas.html", render_atlas_html(atlas))
    active = atlas["locations"][atlas["active_location_id"]]
    packet = {
        "schema": "axm.location-export-packet.v1",
        "map_id": atlas["map_id"],
        "active_location_id": atlas["active_location_id"],
        "location": active,
        "atlas_visit_chain_head": atlas.get("visit_chain_head"),
    }
    packet["packet_sha256"] = canonical_hash(packet, "AXM-LOCATION-EXPORT-PACKET-V1")
    atomic_write_json(output / "location_packet.json", packet)


def render_atlas_html(atlas: dict[str, Any]) -> str:
    payload = json.dumps(atlas, ensure_ascii=False).replace("</", "<\\/")
    title = html.escape(str(atlas.get("map_id", "AXM Expedition Atlas")))
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
:root{{--bg:#05080d;--panel:#0d1822;--line:#294658;--text:#edf6fa;--muted:#9db1bd;--accent:#72dce9;--warm:#efc77b;--frontier:#bd9df4}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at top,#112431,#05080d 55%);color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif}}main{{max-width:1180px;margin:auto;padding:20px}}h1{{font-weight:500;letter-spacing:.07em}}.lead{{color:var(--muted);line-height:1.6;max-width:940px}}.grid{{display:grid;grid-template-columns:1.3fr .7fr;gap:14px}}.card{{background:linear-gradient(180deg,#10202c,var(--panel));border:1px solid var(--line);border-radius:15px;padding:16px}}svg{{width:100%;height:auto;background:#050b10;border:1px solid var(--line);border-radius:12px}}.legend{{display:flex;gap:10px;flex-wrap:wrap;color:var(--muted);font-size:.82rem;margin:10px 0}}.dot{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}}button{{width:100%;text-align:left;border:1px solid var(--line);background:#0b151e;color:var(--text);border-radius:10px;padding:10px;margin:5px 0;cursor:pointer}}button.active{{border-color:var(--accent)}}.metric{{display:grid;grid-template-columns:1fr auto;gap:12px;padding:7px 0;border-bottom:1px solid #203441}}.metric span{{color:var(--muted)}}.badge{{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:4px 8px;color:var(--warm);font-size:.72rem}}.callout{{border-left:3px solid var(--warm);padding:11px 13px;background:#0a131b;color:var(--muted);margin:12px 0}}code{{color:var(--accent);word-break:break-all}}.map-help{{color:var(--muted);font-size:.82rem;line-height:1.5;margin:10px 2px 0}}svg g[data-id]:focus{{outline:none}}svg g[data-id]:focus .node-core{{stroke:#fff;stroke-width:3}}@media(max-width:820px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><main><div class="badge">Mike — Axiom/Mir · v0.7.0</div><h1>Persistent expedition atlas</h1><p class="lead">Real catalog anchors, simulated frontier locations, and crew observations share one map without sharing one truth label. Re-rendering an old expedition can improve the visual experience, but it cannot change the preserved location, visit, or event hashes.</p><div class="callout"><strong>Map is not engine capability:</strong> a coordinate can be visible and selectable while physical travel remains unavailable, delayed, or impossible for the current ship.</div><div class="grid"><section class="card"><svg id="map" viewBox="0 0 760 560" role="img" aria-label="Projected expedition atlas" aria-describedby="map-help"></svg><p id="map-help" class="map-help">Map points are selectable controls. Tab to a point, then press Enter or Space to inspect it. The bright outer ring marks the current map selection.</p><div class="legend"><span><i class="dot" style="background:#72dce9"></i>catalog anchor</span><span><i class="dot" style="background:#bd9df4"></i>procedural frontier</span><span><i class="dot" style="background:#efc77b"></i>visited</span></div></section><section class="card"><h2>Locations</h2><div id="locations"></div><h2 id="name" aria-live="polite"></h2><div id="details"></div></section></div></main><script>
const atlas={payload};const locations=Object.values(atlas.locations);let selected=atlas.active_location_id;const svg=document.getElementById('map');
function project(p){{const max=Math.max(60,...locations.map(l=>Math.hypot(l.cartesian_ly.x_ly,l.cartesian_ly.y_ly)));return [380+(p.x_ly/max)*320,280+(p.y_ly/max)*240]}}
function esc(v){{return String(v).replace(/[&<>\"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]))}}
function selectLocation(id,restoreMapFocus=false){{selected=id;render();if(restoreMapFocus){{const node=[...svg.querySelectorAll('g[data-id]')].find(n=>n.dataset.id===id);if(node)node.focus()}}}}
function draw(){{svg.innerHTML='<circle cx="380" cy="280" r="4" fill="#efc77b"/><line x1="60" y1="280" x2="700" y2="280" stroke="#1c3443"/><line x1="380" y1="40" x2="380" y2="520" stroke="#1c3443"/>';for(const r of atlas.routes){{const a=atlas.locations[r.from_location_id],b=atlas.locations[r.to_location_id];if(!a||!b)continue;const [x1,y1]=project(a.cartesian_ly),[x2,y2]=project(b.cartesian_ly);svg.innerHTML+=`<line x1="${{x1}}" y1="${{y1}}" x2="${{x2}}" y2="${{y2}}" stroke="#294658" stroke-dasharray="5 6"/>`}}for(const l of locations){{const [x,y]=project(l.cartesian_ly);const fill=l.knowledge_class==='catalog_anchor'?'#72dce9':'#bd9df4';const visitedRing=l.visit_count>0?'<circle cx="'+x+'" cy="'+y+'" r="9" fill="none" stroke="#efc77b"/>':'';const selectedRing=l.location_id===selected?'<circle class="selected-ring" cx="'+x+'" cy="'+y+'" r="14" fill="none" stroke="#72dce9" stroke-width="3"/>':'';svg.innerHTML+=`<g data-id="${{esc(l.location_id)}}" tabindex="0" role="button" aria-pressed="${{l.location_id===selected}}" aria-label="${{esc(l.name)}}; ${{esc(l.knowledge_class)}}; ${{l.visit_count}} visit(s)" style="cursor:pointer">${{selectedRing}}${{visitedRing}}<circle class="node-core" cx="${{x}}" cy="${{y}}" r="5" fill="${{fill}}"/><text x="${{x+9}}" y="${{y-8}}" fill="#edf6fa" font-size="11">${{esc(l.name)}}</text></g>`}}svg.querySelectorAll('g[data-id]').forEach(g=>{{const pick=()=>selectLocation(g.dataset.id,true);g.addEventListener('click',pick);g.addEventListener('keydown',e=>{{if(e.key==='Enter'||e.key===' '){{e.preventDefault();pick()}}}})}})}}
function metric(k,v){{return `<div class="metric"><span>${{esc(k)}}</span><strong>${{esc(v)}}</strong></div>`}}
function render(){{document.getElementById('locations').innerHTML=locations.sort((a,b)=>b.visit_count-a.visit_count||a.name.localeCompare(b.name)).map(l=>`<button class="${{l.location_id===selected?'active':''}}" data-id="${{esc(l.location_id)}}">${{esc(l.name)}} · ${{l.knowledge_class}} · ${{l.visit_count}} visit(s)</button>`).join('');document.querySelectorAll('button[data-id]').forEach(b=>b.addEventListener('click',()=>selectLocation(b.dataset.id,false)));const l=atlas.locations[selected];document.getElementById('name').textContent=l.name;document.getElementById('details').innerHTML=metric('Truth layer',l.knowledge_class)+metric('Distance',Number(l.distance_ly.value).toFixed(3)+' ly')+metric('Known worlds',(l.known_worlds||[]).length)+metric('Crew observations',(l.crew_observations||[]).length)+metric('Render revisions',(l.render_history||[]).length)+metric('Physical return',l.route_feasibility.status)+`<p class="lead">${{esc(l.route_feasibility.rule)}}</p><p><code>${{esc(l.authoritative_snapshot_sha256)}}</code></p>`;draw()}}render();
</script></body></html>'''
