from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .atlas import build_expedition_atlas, record_visit, write_atlas_files
from .command import mode_catalog, validate_mode
from .command_console import render_command_console
from .generator import canonical_json
from .live_console import render_live_console
from .runtime import initial_runtime_state
from .validation import validate_system
from .visualizer import render_html


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _managed_names(output: Path) -> list[str]:
    candidates = [
        "system.json",
        "causality_log.jsonl",
        "system.html",
        "runtime_state.json",
        "event_ledger.jsonl",
        "command_ledger.jsonl",
        "adventure_console.html",
        "command_console.html",
        "pending_command_session.json",
        "expedition_atlas.json",
        "atlas.html",
        "location_packet.json",
    ]
    names = [name for name in candidates if (output / name).exists()]
    sessions = output / "command_sessions"
    if sessions.exists():
        names.extend(str(path.relative_to(output)) for path in sorted(sessions.rglob("*.json")))
    revisit_packets = output / "revisit_packets"
    if revisit_packets.exists():
        names.extend(str(path.relative_to(output)) for path in sorted(revisit_packets.rglob("*.json")))
    return names


def _manifest_for(output: Path, names: list[str] | None = None) -> dict[str, Any]:
    names = names or _managed_names(output)
    return {
        "schema": "axm.output-manifest.v3",
        "files": {name: sha256_file(output / name) for name in names if (output / name).exists()},
    }




def refresh_output_manifest(output: Path) -> dict[str, Any]:
    """Rebuild the output manifest after atlas-only operations."""
    return _write_manifest(output)

def load_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            result.append(json.loads(line))
    return result


def load_pending_session(output: Path) -> dict[str, Any] | None:
    path = output / "pending_command_session.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _refresh_consoles(output: Path, system: dict[str, Any], state: dict[str, Any]) -> None:
    ledger = load_ledger(output / "event_ledger.jsonl")
    pending = load_pending_session(output)
    (output / "adventure_console.html").write_text(render_live_console(system, state, ledger), encoding="utf-8")
    (output / "command_console.html").write_text(
        render_command_console(system, state, ledger, pending), encoding="utf-8"
    )


def _write_manifest(output: Path) -> dict[str, Any]:
    manifest = _manifest_for(output)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def write_system(
    output: Path,
    data: dict[str, Any],
    command_mode: str = "autonomous_deterministic",
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    validate_mode(command_mode)
    data["active_command_mode"] = command_mode
    data["command_architecture"] = {
        "schema": "axm.command-architecture.v1",
        "modes": mode_catalog(),
        "shared_crew_rule": (
            "All four modes use the same deterministic crew assessment and execution layer; only command authority changes."
        ),
        "collaboration_rule": (
            "Human and AI each receive one explicit vote. Different votes open discussion and cannot be auto-resolved."
        ),
    }
    warnings = validate_system(data)
    data["integrity"] = {
        "canonical_state_sha256": hashlib.sha256(
            canonical_json({**data, "generated_at": "<excluded>"}).encode("utf-8")
        ).hexdigest(),
        "validation_warnings": warnings,
    }
    runtime_state = initial_runtime_state(data)

    system_path = output / "system.json"
    log_path = output / "causality_log.jsonl"
    html_path = output / "system.html"
    runtime_path = output / "runtime_state.json"
    event_path = output / "event_ledger.jsonl"
    command_path = output / "command_ledger.jsonl"

    system_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    log_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in data["causality"]) + "\n", encoding="utf-8")
    html_path.write_text(render_html(data), encoding="utf-8")
    runtime_path.write_text(json.dumps(runtime_state, indent=2, ensure_ascii=False), encoding="utf-8")
    event_path.write_text("", encoding="utf-8")
    command_path.write_text("", encoding="utf-8")
    pending = output / "pending_command_session.json"
    if pending.exists():
        pending.unlink()
    _refresh_consoles(output, data, runtime_state)
    atlas = build_expedition_atlas(data)
    write_atlas_files(output, atlas)
    return _write_manifest(output)


def save_pending_session(output: Path, session: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    path = output / "pending_command_session.json"
    path.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")
    state = json.loads(json.dumps(state))
    state.setdefault("command", {})["pending_session_id"] = session["session_id"]
    (output / "runtime_state.json").write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    system = json.loads((output / "system.json").read_text(encoding="utf-8"))
    _refresh_consoles(output, system, state)
    return _write_manifest(output)


def clear_pending_session(output: Path) -> None:
    path = output / "pending_command_session.json"
    if path.exists():
        path.unlink()


def append_runtime_event(output: Path, event: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    system = json.loads((output / "system.json").read_text(encoding="utf-8"))
    ledger_path = output / "event_ledger.jsonl"
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    with (output / "command_ledger.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "event_id": event["event_id"],
            "turn": event["turn"],
            "event_hash": event["event_hash"],
            "record_hash": event.get("record_hash"),
            "command": event.get("command"),
        }, ensure_ascii=False) + "\n")
    pending = load_pending_session(output)
    if pending and event.get("command", {}).get("discussion_session_id") == pending.get("session_id"):
        archive = output / "command_sessions"
        archive.mkdir(parents=True, exist_ok=True)
        archived = {**pending, "status": "resolved", "resolved_event_id": event["event_id"], "resolved_event_hash": event["event_hash"]}
        (archive / f"{pending['session_id']}.json").write_text(json.dumps(archived, indent=2, ensure_ascii=False), encoding="utf-8")
    clear_pending_session(output)
    state.setdefault("command", {})["pending_session_id"] = None
    (output / "runtime_state.json").write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    atlas_path = output / "expedition_atlas.json"
    if atlas_path.exists():
        atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
        atlas = record_visit(atlas, atlas["active_location_id"], event)
        write_atlas_files(output, atlas)
    _refresh_consoles(output, system, state)
    return _write_manifest(output)


def update_command_mode(output: Path, mode: str) -> dict[str, Any]:
    validate_mode(mode)
    if load_ledger(output / "event_ledger.jsonl"):
        raise ValueError("command mode can only be changed before the first resolved event; create a new branch for later mode changes")
    if load_pending_session(output):
        raise ValueError("cannot change command mode while a command council session is pending")
    system_path = output / "system.json"
    state_path = output / "runtime_state.json"
    system = json.loads(system_path.read_text(encoding="utf-8"))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    system["active_command_mode"] = mode
    system["integrity"]["canonical_state_sha256"] = hashlib.sha256(
        canonical_json({**system, "generated_at": "<excluded>", "integrity": {**system.get("integrity", {}), "canonical_state_sha256": "<excluded>"}}).encode("utf-8")
    ).hexdigest()
    state.setdefault("command", {})["active_mode"] = mode
    system_path.write_text(json.dumps(system, indent=2, ensure_ascii=False), encoding="utf-8")
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    _refresh_consoles(output, system, state)
    return _write_manifest(output)
