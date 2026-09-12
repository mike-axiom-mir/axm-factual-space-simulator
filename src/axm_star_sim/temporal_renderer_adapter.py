from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any

from .bridge_visual_core import make_reconstruction_packet, pin_start_package_for_save, resolve_start_package
from .generator import canonical_json


ADAPTER_VERSION = "0.14.0"
REQUIRED_SOURCE_FILES = ("system.json", "runtime_state.json", "event_ledger.jsonl")
ALLOWED_SYSTEM_SCHEMAS = {"axm.star-system.v2"}
ALLOWED_RUNTIME_SCHEMAS = {"axm.adventure-runtime.v4"}
ALLOWED_EVENT_SCHEMAS = {"axm.adventure-event.v4"}


def canonical_hash(value: Any, domain: str) -> str:
    return hashlib.sha256(f"{domain}|{canonical_json(value)}".encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_bytes(value: bytes, name: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{name} is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{name} must contain a JSON object")
    return parsed


def parse_event_ledger(value: bytes) -> list[dict[str, Any]]:
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"event_ledger.jsonl is not valid UTF-8: {exc}") from exc
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"event_ledger.jsonl line {line_number} is invalid JSON: {exc}") from exc
        if not isinstance(event, dict):
            raise ValueError(f"event_ledger.jsonl line {line_number} must be a JSON object")
        events.append(event)
    return events


def verify_main_simulator_snapshot(
    *,
    system_bytes: bytes,
    runtime_bytes: bytes,
    event_ledger_bytes: bytes,
    manifest_bytes: bytes,
    source_repository: str,
    source_commit: str,
) -> dict[str, Any]:
    """Verify a read-only subset imported from a main-simulator output folder.

    This adapter verifies exact manifest hashes and event-chain links. It does
    not pretend to replace the main repository's semantic event verifier.
    """

    source_files = {
        "system.json": system_bytes,
        "runtime_state.json": runtime_bytes,
        "event_ledger.jsonl": event_ledger_bytes,
    }
    file_hashes = {name: sha256_bytes(value) for name, value in source_files.items()}
    failures: list[str] = []
    warnings = [
        "Only the named renderer-input subset is verified; this is not a whole-repository seal.",
        "Event links are checked, but event hashes must still be semantically revalidated by the main simulator.",
    ]
    system: dict[str, Any] = {}
    runtime: dict[str, Any] = {}
    events: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {}

    try:
        system = _json_bytes(system_bytes, "system.json")
        runtime = _json_bytes(runtime_bytes, "runtime_state.json")
        events = parse_event_ledger(event_ledger_bytes)
        manifest = _json_bytes(manifest_bytes, "manifest.json")
    except ValueError as exc:
        failures.append(str(exc))

    manifest_files = manifest.get("files", {}) if isinstance(manifest, dict) else {}
    if manifest and manifest.get("schema") != "axm.output-manifest.v3":
        failures.append("unsupported source manifest schema")
    if not isinstance(manifest_files, dict):
        failures.append("source manifest files field must be an object")
        manifest_files = {}
    for name, digest in file_hashes.items():
        expected = manifest_files.get(name)
        if expected is None:
            failures.append(f"source manifest does not manage {name}")
        elif expected != digest:
            failures.append(f"source manifest hash mismatch for {name}")

    if system:
        if system.get("schema_version") not in ALLOWED_SYSTEM_SCHEMAS:
            failures.append("unsupported system schema")
        if not system.get("system_id"):
            failures.append("system id missing")
    if runtime:
        if runtime.get("schema") not in ALLOWED_RUNTIME_SCHEMAS:
            failures.append("unsupported runtime schema")
        if runtime.get("system_id") != system.get("system_id"):
            failures.append("runtime belongs to a different system")

    seen_ids: set[str] = set()
    previous_hash: str | None = None
    previous_turn: int | None = None
    for index, event in enumerate(events):
        label = f"event[{index}]"
        if event.get("schema") not in ALLOWED_EVENT_SCHEMAS:
            failures.append(f"{label} has unsupported schema")
        if event.get("system_id") != system.get("system_id"):
            failures.append(f"{label} belongs to a different system")
        event_id = str(event.get("event_id", ""))
        if not event_id:
            failures.append(f"{label} event id missing")
        elif event_id in seen_ids:
            failures.append(f"{label} duplicates event id {event_id}")
        seen_ids.add(event_id)
        turn = event.get("turn")
        if not isinstance(turn, int):
            failures.append(f"{label} turn must be an integer")
        elif previous_turn is not None and turn <= previous_turn:
            failures.append(f"{label} turn is not strictly increasing")
        if event.get("previous_event_hash") != previous_hash:
            failures.append(f"{label} previous-event link mismatch")
        event_hash = event.get("event_hash")
        if not isinstance(event_hash, str) or len(event_hash) != 64:
            failures.append(f"{label} event hash missing or malformed")
        previous_hash = event_hash if isinstance(event_hash, str) else None
        previous_turn = turn if isinstance(turn, int) else previous_turn

    if events and runtime.get("last_event_hash") != previous_hash:
        failures.append("runtime last_event_hash does not match imported ledger head")
    if events and runtime.get("turn") != events[-1].get("turn"):
        failures.append("runtime turn does not match imported ledger head")

    packet = {
        "schema": "axm.main-simulator-renderer-import-receipt.v1",
        "adapter_version": ADAPTER_VERSION,
        "status": "IMPORT_VALID" if not failures else "HOLD_IMPORT_INVALID",
        "source_repository": source_repository,
        "source_commit": source_commit,
        "source_manifest_sha256": sha256_bytes(manifest_bytes),
        "verified_source_files": file_hashes,
        "system_id": system.get("system_id"),
        "system_name": system.get("name"),
        "runtime_turn": runtime.get("turn"),
        "event_count": len(events),
        "ledger_head_hash": previous_hash,
        "verification_scope": "selected_file_hashes_plus_event_chain_links",
        "main_semantic_verifier_status": "required_before_merge",
        "failures": failures,
        "warnings": warnings,
        "authority": "read_only_renderer_input",
        "may_modify_source_files": False,
        "may_modify_world_state": False,
        "may_append_events": False,
    }
    packet["receipt_hash"] = canonical_hash(packet, "AXM-MAIN-SIMULATOR-RENDERER-IMPORT-V1")
    return packet


def load_verified_snapshot(
    *,
    system_bytes: bytes,
    runtime_bytes: bytes,
    event_ledger_bytes: bytes,
    manifest_bytes: bytes,
    source_repository: str,
    source_commit: str,
) -> dict[str, Any]:
    receipt = verify_main_simulator_snapshot(
        system_bytes=system_bytes,
        runtime_bytes=runtime_bytes,
        event_ledger_bytes=event_ledger_bytes,
        manifest_bytes=manifest_bytes,
        source_repository=source_repository,
        source_commit=source_commit,
    )
    if receipt["status"] != "IMPORT_VALID":
        raise ValueError("main simulator import is on HOLD: " + "; ".join(receipt["failures"]))
    return {
        "system": _json_bytes(system_bytes, "system.json"),
        "runtime": _json_bytes(runtime_bytes, "runtime_state.json"),
        "events": parse_event_ledger(event_ledger_bytes),
        "import_receipt": receipt,
    }


def build_renderer_authorization(
    import_receipt: dict[str, Any],
    target_render_profile_id: str = "axm.render.temporal-evidence-bridge.v1",
) -> dict[str, Any]:
    """Bind the candidate to the main simulator's existing renderer gate."""

    if import_receipt.get("status") != "IMPORT_VALID":
        raise ValueError("a valid renderer import receipt is required")
    runtime_hash = import_receipt.get("verified_source_files", {}).get("runtime_state.json")
    if not isinstance(runtime_hash, str) or len(runtime_hash) != 64:
        raise ValueError("verified runtime state hash is required")
    start_pin = pin_start_package_for_save(resolve_start_package())
    reconstruction = make_reconstruction_packet(
        start_pin,
        historical_state_hash=runtime_hash,
        target_render_profile_id=target_render_profile_id,
    )
    packet = {
        "schema": "axm.temporal-renderer-authorization.v1",
        "adapter_version": ADAPTER_VERSION,
        "source_import_receipt_hash": import_receipt["receipt_hash"],
        "source_runtime_state_sha256": runtime_hash,
        "target_render_profile_id": target_render_profile_id,
        "start_pin_receipt": start_pin["pin_receipt"],
        "reconstruction_packet": reconstruction,
        "authority": "renderer_authorized_presentation_only",
        "may_modify_world_state": False,
        "may_modify_history": False,
    }
    packet["authorization_receipt"] = canonical_hash(packet, "AXM-TEMPORAL-RENDERER-AUTHORIZATION-V1")
    return packet


def _finite_number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _optional_finite_number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def derive_mission_time_receipts(
    events: list[dict[str, Any]],
    runtime_mission_time_hours: Any,
) -> dict[str, Any]:
    """Reconstruct bounded receipt ranges without creating mission authority.

    The runtime clock is copied as source state. Per-event ranges are derived
    only when every recorded mission-time delta can reconcile exactly with the
    current runtime clock. Missing data produces a hold rather than an invented
    timestamp. Wall-clock age remains unknown unless another system supplies a
    separately verified timestamp.
    """

    current = _optional_finite_number(runtime_mission_time_hours)
    failures: list[str] = []
    durations: list[float | None] = []
    for index, event in enumerate(events):
        raw_duration = event.get("outcome", {}).get("resource_deltas", {}).get("mission_time_hours")
        duration = _optional_finite_number(raw_duration)
        if duration is None:
            failures.append(f"event[{index}] mission-time delta is missing or non-finite")
        elif duration < 0:
            failures.append(f"event[{index}] mission-time delta is negative")
        durations.append(duration)

    if current is None:
        failures.append("runtime mission time is missing or non-finite")
    elif current < 0:
        failures.append("runtime mission time is negative")

    known_total = sum(value for value in durations if value is not None)
    origin = None if current is None or failures else current - known_total
    if origin is not None and origin < -1e-9:
        failures.append("recorded event durations exceed the runtime mission clock")
        origin = None
    if origin is not None and abs(origin) < 1e-9:
        origin = 0.0

    rows: list[dict[str, Any]] = []
    running = origin
    for index, event in enumerate(events):
        duration = durations[index]
        start = running if running is not None and duration is not None and not failures else None
        end = start + duration if start is not None and duration is not None else None
        if end is not None:
            running = end
        timestamp_present = bool(event.get("timestamp") or event.get("created_at"))
        rows.append({
            "event_id": event.get("event_id"),
            "turn": event.get("turn"),
            "mission_time_start_hours": None if start is None else round(start, 9),
            "mission_time_end_hours": None if end is None else round(end, 9),
            "mission_duration_hours": duration,
            "mission_time_delta_to_current_hours": (
                None if end is None or current is None else round(end - current, 9)
            ),
            "temporal_relation": "ledger_head" if index == len(events) - 1 else "historical",
            "wall_clock_age_status": (
                "UNASSESSED_TIMESTAMP_PRESENT" if timestamp_present else "UNKNOWN_NO_TIMESTAMP"
            ),
            "truth_type": "derived-simulation-state",
            "authority": "presentation_receipt_only",
            "may_advance_mission_time": False,
        })

    if not failures and current is not None and running is not None and abs(running - current) > 1e-9:
        failures.append("reconstructed ledger end does not match runtime mission time")
        for row in rows:
            row["mission_time_start_hours"] = None
            row["mission_time_end_hours"] = None
            row["mission_time_delta_to_current_hours"] = None

    packet = {
        "schema": "axm.main-simulator-temporal-reconstruction.v1",
        "status": "CONSISTENT_RECONSTRUCTION" if not failures else "HOLD_TEMPORAL_RECONSTRUCTION",
        "source_current_mission_time_hours": current,
        "derived_origin_mission_time_hours": None if failures else origin,
        "recorded_duration_total_hours": round(known_total, 9),
        "receipts": rows,
        "future_receipt_status": "NONE_IN_IMPORTED_LEDGER_NOT_A_PREDICTION",
        "wall_clock_freshness_status": "UNKNOWN_WITHOUT_VERIFIED_OBSERVATION_TIMESTAMPS",
        "clock_separation": "source_mission_clock_is_distinct_from_renderer_display_clock",
        "truth_type": "derived-simulation-state",
        "failures": failures,
        "authority": "presentation_reconstruction_only",
        "may_advance_mission_time": False,
        "may_append_event": False,
    }
    packet["reconstruction_hash"] = canonical_hash(
        packet,
        "AXM-MAIN-SIMULATOR-TEMPORAL-RECONSTRUCTION-V1",
    )
    return packet


RESOURCE_DELTA_ORDER = (
    "mission_time_hours",
    "reactor_reserve_percent",
    "sensor_health_percent",
    "hull_integrity_percent",
    "fuel_percent",
    "heat_percent",
    "probe_count",
    "knowledge_points",
)

RESOURCE_DELTA_UNITS = {
    "mission_time_hours": "h",
    "reactor_reserve_percent": "percentage_point",
    "sensor_health_percent": "percentage_point",
    "hull_integrity_percent": "percentage_point",
    "fuel_percent": "percentage_point",
    "heat_percent": "percentage_point",
    "probe_count": "count",
    "knowledge_points": "point",
}


def build_event_state_change_receipt(event: dict[str, Any]) -> dict[str, Any]:
    """Expose recorded event deltas as read-only presentation evidence."""

    raw = event.get("outcome", {}).get("resource_deltas", {})
    failures: list[str] = []
    if not isinstance(raw, dict):
        failures.append("outcome.resource_deltas must be an object")
        raw = {}
    ordered_keys = [key for key in RESOURCE_DELTA_ORDER if key in raw]
    ordered_keys.extend(sorted(key for key in raw if key not in RESOURCE_DELTA_ORDER))
    changes: list[dict[str, Any]] = []
    for key in ordered_keys:
        value = _optional_finite_number(raw.get(key))
        if value is None:
            failures.append(f"resource delta {key} is non-finite")
        changes.append({
            "resource_id": key,
            "delta": value,
            "unit": RESOURCE_DELTA_UNITS.get(key, "source_unit_unspecified"),
            "direction": (
                "unknown" if value is None else "increase" if value > 0 else "decrease" if value < 0 else "no_change"
            ),
            "truth_type": "recorded-simulation-event-delta",
            "source_path": f"outcome.resource_deltas.{key}",
            "authority": "read_only_event_receipt",
            "value_judgment": "not_assigned",
            "may_modify_runtime_resource": False,
        })
    if not changes:
        failures.append("event contains no resource deltas")
    packet = {
        "schema": "axm.main-simulator-event-state-change-receipt.v1",
        "status": "STATE_CHANGES_VALID" if not failures else "HOLD_STATE_CHANGES_INVALID",
        "event_id": event.get("event_id"),
        "turn": event.get("turn"),
        "changes": changes,
        "failures": failures,
        "authority": "presentation_receipt_only",
        "may_modify_world_state": False,
        "may_modify_runtime_resources": False,
        "may_append_event": False,
    }
    packet["receipt_hash"] = canonical_hash(
        packet,
        "AXM-MAIN-SIMULATOR-EVENT-STATE-CHANGE-RECEIPT-V1",
    )
    return packet


def build_temporal_storyboard(snapshot: dict[str, Any]) -> dict[str, Any]:
    receipt = snapshot.get("import_receipt", {})
    if receipt.get("status") != "IMPORT_VALID":
        raise ValueError("a valid import receipt is required")
    system = copy.deepcopy(snapshot["system"])
    runtime = copy.deepcopy(snapshot["runtime"])
    events = copy.deepcopy(snapshot["events"])

    planets = []
    for planet in system.get("planets", []):
        facts = planet.get("facts", {})
        semi_major = facts.get("semi_major_axis", {})
        period = facts.get("orbital_period", {})
        planets.append({
            "planet_id": planet.get("id"),
            "name": planet.get("name"),
            "kind": planet.get("kind"),
            "semi_major_axis_au": _finite_number(semi_major.get("value")),
            "semi_major_axis_truth_type": semi_major.get("truth_type", "unknown"),
            "orbital_period_days": _finite_number(period.get("value")),
            "orbital_period_truth_type": period.get("truth_type", "unknown"),
            "initial_display_phase_deg": _finite_number(planet.get("visual", {}).get("phase_deg")),
            "size_hint": _finite_number(planet.get("visual", {}).get("size_hint"), 4.0),
            "render_motion": "compressed_circular_presentation_from_source_values",
            "position_authority": "presentation_only_simulation_geometry",
            "precision_ephemeris_claimed": False,
        })

    temporal_reconstruction = derive_mission_time_receipts(
        events,
        runtime.get("mission_time_hours"),
    )
    temporal_rows = temporal_reconstruction["receipts"]
    cues = []
    for index, event in enumerate(events):
        physics = event.get("physics_expectation", {})
        communications = physics.get("communications", {})
        outcome = event.get("outcome", {})
        observation = outcome.get("observation", {})
        interpretation = outcome.get("interpretation", {})
        temporal = copy.deepcopy(temporal_rows[index])
        state_changes = build_event_state_change_receipt(event)
        cues.append({
            "cue_id": f"cue:{event.get('event_id', index)}",
            "display_index": index,
            "turn": event.get("turn"),
            "source_event_id": event.get("event_id"),
            "source_event_hash": event.get("event_hash"),
            "action": event.get("action"),
            "action_category": event.get("action_category"),
            "target_planet_id": physics.get("target_planet_id"),
            "target_planet_name": physics.get("target_planet_name"),
            "outcome_id": outcome.get("id"),
            "outcome_title": outcome.get("title"),
            "observation": observation.get("statement"),
            "observation_truth_type": observation.get("truth_type", "unknown"),
            "interpretation": interpretation.get("statement"),
            "interpretation_truth_type": interpretation.get("truth_type", "unknown"),
            "one_way_light_time_s": _finite_number(communications.get("one_way_light_time_s")),
            "transmit_duration_s": _finite_number(communications.get("transmit_duration_s")),
            "earliest_full_response_s": _finite_number(communications.get("earliest_full_response_s")),
            "temporal_receipt": temporal,
            "state_change_receipt": state_changes,
            "playback_segments": [
                {"id": "command_outbound", "display_fraction": 0.30},
                {"id": "observation_window", "display_fraction": 0.24},
                {"id": "telemetry_return", "display_fraction": 0.46},
            ],
            "time_mapping": "compressed_explanatory_sequence_not_physical_duration",
            "authority": "presentation_cue_from_immutable_event",
            "may_change_event": False,
        })

    storyboard = {
        "schema": "axm.main-simulator-temporal-storyboard.v1",
        "version": ADAPTER_VERSION,
        "source_import_receipt_hash": receipt["receipt_hash"],
        "system_id": system.get("system_id"),
        "system_name": system.get("name"),
        "star_visual_temperature_hint": system.get("star", {}).get("visual_temperature_hint"),
        "ship_orbit_au": _finite_number(runtime.get("navigation", {}).get("ship_orbit_au")),
        "runtime_turn": runtime.get("turn"),
        "mission_time_hours": runtime.get("mission_time_hours"),
        "mission_clock_authority": "copied_read_only_runtime_source_state",
        "temporal_reconstruction": temporal_reconstruction,
        "planets": planets,
        "cues": cues,
        "current_resources": copy.deepcopy(runtime.get("resources", {})),
        "presentation_profiles": {
            "camera_presets": [
                {
                    "id": "overview",
                    "label": "System overview",
                    "authority": "presentation_only",
                    "changes_semantics": False,
                },
                {
                    "id": "target_focus",
                    "label": "Target focus",
                    "authority": "presentation_only",
                    "changes_semantics": False,
                },
                {
                    "id": "signal_lane",
                    "label": "Signal lane",
                    "authority": "presentation_only",
                    "changes_semantics": False,
                },
            ],
            "default_camera_preset": "overview",
            "label_modes": ["focus", "all", "minimal"],
            "default_label_mode": "focus",
            "replay_scrubber": {
                "display_seconds_per_cue": 8.0,
                "authority": "presentation_only",
                "may_advance_mission_time": False,
                "may_append_event": False,
            },
            "object_inspector": {
                "source_objects": "storyboard_planets_only",
                "default_mode": "follow_active_event_target",
                "authority": "presentation_only",
                "may_retarget_event": False,
                "may_change_truth_labels": False,
            },
            "may_change_world_state": False,
            "may_change_history": False,
            "may_change_truth_labels": False,
        },
        "authority": "presentation_storyboard_only",
        "cannot_modify": [
            "source files",
            "world state",
            "event ledger",
            "command authority",
            "truth labels",
            "claim ceilings",
            "route feasibility",
        ],
        "truth_note": (
            "Orbit motion, signal travel, and cue timing are compressed explanatory animation. "
            "Source values and immutable event receipts remain separate and unchanged. "
            "The source mission clock is visually separated from the renderer display clock. "
            "Replay scrubbing, object inspection, and state-change bars remain presentation only."
        ),
    }
    storyboard["storyboard_hash"] = canonical_hash(storyboard, "AXM-MAIN-SIMULATOR-TEMPORAL-STORYBOARD-V1")
    return storyboard


def sample_storyboard(storyboard: dict[str, Any], elapsed_seconds: float, *, seconds_per_cue: float = 8.0) -> dict[str, Any]:
    cues = storyboard.get("cues", [])
    elapsed = max(0.0, _finite_number(elapsed_seconds))
    duration = max(0.25, _finite_number(seconds_per_cue, 8.0))
    if not cues:
        packet = {
            "schema": "axm.main-simulator-storyboard-sample.v1",
            "status": "HOLD_NO_EVENTS",
            "elapsed_display_seconds": elapsed,
            "authority": "presentation_state_only",
        }
        packet["sample_hash"] = canonical_hash(packet, "AXM-MAIN-SIMULATOR-STORYBOARD-SAMPLE-V1")
        return packet
    cycle = elapsed / duration
    cue_index = int(cycle) % len(cues)
    phase = cycle - math.floor(cycle)
    if phase < 0.30:
        segment = "command_outbound"
        segment_phase = phase / 0.30
    elif phase < 0.54:
        segment = "observation_window"
        segment_phase = (phase - 0.30) / 0.24
    else:
        segment = "telemetry_return"
        segment_phase = (phase - 0.54) / 0.46
    packet = {
        "schema": "axm.main-simulator-storyboard-sample.v1",
        "status": "PLAYBACK_SAMPLE",
        "elapsed_display_seconds": elapsed,
        "seconds_per_cue": duration,
        "cue_index": cue_index,
        "cue_id": cues[cue_index]["cue_id"],
        "normalized_cue_phase": phase,
        "active_segment": segment,
        "normalized_segment_phase": max(0.0, min(1.0, segment_phase)),
        "source_event_hash": cues[cue_index]["source_event_hash"],
        "time_mapping": "compressed_explanatory_sequence_not_physical_duration",
        "authority": "presentation_state_only",
        "may_advance_mission_time": False,
        "may_append_event": False,
    }
    packet["sample_hash"] = canonical_hash(packet, "AXM-MAIN-SIMULATOR-STORYBOARD-SAMPLE-V1")
    return packet


def migrate_v011_session_state(state: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(state)
    original_version = str(result.get("version", "unknown"))
    result["schema"] = "axm.globe-session-state.v6"
    result["version"] = ADAPTER_VERSION
    result.setdefault("mainSimulatorBridge", {
        "source": "embedded_verified_fixture",
        "playing": False,
        "speed": 1.0,
        "selectedCueIndex": 0,
        "reducedMotion": False,
        "authority": "presentation_state_only",
    })
    result["migration_receipts"] = [
        *result.get("migration_receipts", []),
        {
            "from_version": original_version,
            "to_version": ADAPTER_VERSION,
            "kind": "additive_main_simulator_renderer_bridge_state",
            "preserved_original_fields": True,
        },
    ]
    return result
