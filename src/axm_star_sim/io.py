from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .atlas import build_expedition_atlas, record_visit, verify_visit_chain, write_atlas_files
from .command import mode_catalog, validate_mode
from .command_console import render_command_console
from .generator import canonical_json
from .live_console import render_live_console
from .runtime import canonical_hash, initial_runtime_state, verify_ledger
from .storage import atomic_write_json as _atomic_write_json
from .storage import atomic_write_text as _atomic_write_text
from .storage import remove_file as _remove_file
from .validation import validate_system
from .visualizer import render_html


RUNTIME_COMMIT_SCHEMA = "axm.runtime-commit.v1"
RUNTIME_COMMIT_NAME = ".runtime_commit.json"


class RuntimeCommitError(ValueError):
    """Raised when a runtime commit cannot be completed without rewriting truth."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_ledger(path: Path, records: list[dict[str, Any]]) -> None:
    text = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    _atomic_write_text(path, text)


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
    _atomic_write_text(output / "adventure_console.html", render_live_console(system, state, ledger))
    _atomic_write_text(output / "command_console.html", render_command_console(system, state, ledger, pending))


def _write_manifest(output: Path) -> dict[str, Any]:
    manifest = _manifest_for(output)
    _atomic_write_json(output / "manifest.json", manifest)
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
    _remove_file(path)


def _command_record(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event["event_id"],
        "turn": event["turn"],
        "event_hash": event["event_hash"],
        "record_hash": event.get("record_hash"),
        "command": event.get("command"),
    }


def _commit_hash(commit: dict[str, Any]) -> str:
    body = {key: value for key, value in commit.items() if key != "commit_sha256"}
    return hashlib.sha256(
        ("AXM-RUNTIME-COMMIT-V1\n" + canonical_json(body)).encode("utf-8")
    ).hexdigest()


def _same_json(left: Any, right: Any) -> bool:
    return canonical_json(left) == canonical_json(right)


def _validate_runtime_commit(system: dict[str, Any], commit: dict[str, Any]) -> list[dict[str, Any]]:
    if commit.get("schema") != RUNTIME_COMMIT_SCHEMA:
        raise RuntimeCommitError("unsupported runtime commit schema")
    if commit.get("commit_sha256") != _commit_hash(commit):
        raise RuntimeCommitError("runtime commit seal is invalid")
    prior_events = commit.get("prior_events")
    event = commit.get("event")
    state_after = commit.get("state_after")
    if not isinstance(prior_events, list) or not isinstance(event, dict) or not isinstance(state_after, dict):
        raise RuntimeCommitError("runtime commit is missing typed event or state data")
    if commit.get("prior_event_count") != len(prior_events):
        raise RuntimeCommitError("runtime commit prior event count is invalid")
    expected_head = prior_events[-1].get("event_hash") if prior_events else None
    if commit.get("prior_event_head") != expected_head:
        raise RuntimeCommitError("runtime commit prior event head is invalid")
    valid, checks, rebuilt = verify_ledger(system, [*prior_events, event])
    if not valid:
        raise RuntimeCommitError(f"runtime commit event failed deterministic replay: {checks[-1]}")
    if canonical_hash(rebuilt) != canonical_hash(state_after):
        raise RuntimeCommitError("runtime commit state does not match deterministic replay")
    if commit.get("command_record") != _command_record(event):
        raise RuntimeCommitError("runtime commit command projection does not match its event")
    atlas_before = commit.get("atlas_before")
    atlas_after = commit.get("atlas_after")
    if (atlas_before is None) != (atlas_after is None):
        raise RuntimeCommitError("runtime commit atlas pair is incomplete")
    if atlas_after is not None:
        if not verify_visit_chain(atlas_before)["valid"] or not verify_visit_chain(atlas_after)["valid"]:
            raise RuntimeCommitError("runtime commit contains an invalid atlas visit chain")
        before_visits = atlas_before.get("visits", [])
        after_visits = atlas_after.get("visits", [])
        if len(after_visits) != len(before_visits) + 1:
            raise RuntimeCommitError("runtime commit must append exactly one atlas visit")
        visit = after_visits[-1]
        if visit.get("event_id") != event.get("event_id") or visit.get("event_hash") != event.get("event_hash"):
            raise RuntimeCommitError("runtime commit atlas visit is not bound to its event")
        if not _same_json(before_visits, after_visits[:-1]):
            raise RuntimeCommitError("runtime commit rewrites prior atlas visits")
    return [*prior_events, event]


def _apply_runtime_commit(output: Path, commit: dict[str, Any]) -> dict[str, Any]:
    system = json.loads((output / "system.json").read_text(encoding="utf-8"))
    target_events = _validate_runtime_commit(system, commit)
    ledger_path = output / "event_ledger.jsonl"
    current_events = load_ledger(ledger_path)
    prior_events = commit["prior_events"]
    if not (_same_json(current_events, prior_events) or _same_json(current_events, target_events)):
        raise RuntimeCommitError("event ledger diverged from the sealed runtime commit")

    # The event ledger is canonical. All writes after it are projections that this
    # sealed commit can reproduce exactly after interruption.
    _atomic_write_ledger(ledger_path, target_events)
    _atomic_write_ledger(output / "command_ledger.jsonl", [_command_record(item) for item in target_events])

    pending = load_pending_session(output)
    sealed_pending = commit.get("pending_session")
    if pending is not None and not _same_json(pending, sealed_pending):
        raise RuntimeCommitError("pending command session diverged from the sealed runtime commit")
    event = commit["event"]
    if sealed_pending and (event.get("command") or {}).get("discussion_session_id") == sealed_pending.get("session_id"):
        archive = output / "command_sessions"
        archive.mkdir(parents=True, exist_ok=True)
        archived = {
            **sealed_pending,
            "status": "resolved",
            "resolved_event_id": event["event_id"],
            "resolved_event_hash": event["event_hash"],
        }
        archive_path = archive / f"{sealed_pending['session_id']}.json"
        if archive_path.exists():
            existing_archive = json.loads(archive_path.read_text(encoding="utf-8"))
            if not _same_json(existing_archive, archived):
                raise RuntimeCommitError("archived command session diverged from the sealed runtime commit")
        _atomic_write_json(archive_path, archived)
    clear_pending_session(output)

    state = copy.deepcopy(commit["state_after"])
    state.setdefault("command", {})["pending_session_id"] = None
    _atomic_write_json(output / "runtime_state.json", state)
    atlas_path = output / "expedition_atlas.json"
    if commit.get("atlas_after") is not None:
        current_atlas = json.loads(atlas_path.read_text(encoding="utf-8"))
        if not (
            _same_json(current_atlas, commit["atlas_before"])
            or _same_json(current_atlas, commit["atlas_after"])
        ):
            raise RuntimeCommitError("expedition atlas diverged from the sealed runtime commit")
        write_atlas_files(output, commit["atlas_after"])
    _refresh_consoles(output, system, state)
    manifest = _write_manifest(output)
    _remove_file(output / RUNTIME_COMMIT_NAME)
    return manifest


def recover_runtime_commit(output: Path) -> dict[str, Any] | None:
    """Finish an interrupted event commit, or fail closed on any divergence."""
    path = output / RUNTIME_COMMIT_NAME
    if not path.exists():
        return None
    try:
        commit = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeCommitError("runtime commit record is unreadable; preserved for inspection") from exc
    return _apply_runtime_commit(output, commit)


def append_runtime_event(output: Path, event: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    if (output / RUNTIME_COMMIT_NAME).exists():
        recover_runtime_commit(output)
    system = json.loads((output / "system.json").read_text(encoding="utf-8"))
    prior_events = load_ledger(output / "event_ledger.jsonl")
    valid, checks, rebuilt = verify_ledger(system, [*prior_events, event])
    if not valid:
        raise RuntimeCommitError(f"new event failed deterministic replay: {checks[-1]}")
    state = copy.deepcopy(state)
    state.setdefault("command", {})["pending_session_id"] = None
    if canonical_hash(rebuilt) != canonical_hash(state):
        raise RuntimeCommitError("supplied runtime state does not match deterministic replay")

    atlas_path = output / "expedition_atlas.json"
    atlas_before = None
    atlas_after = None
    if atlas_path.exists():
        atlas_before = json.loads(atlas_path.read_text(encoding="utf-8"))
        if not verify_visit_chain(atlas_before)["valid"]:
            raise RuntimeCommitError("existing expedition atlas visit chain is invalid")
        atlas_after = record_visit(atlas_before, atlas_before["active_location_id"], event)

    commit = {
        "schema": RUNTIME_COMMIT_SCHEMA,
        "prior_event_count": len(prior_events),
        "prior_event_head": prior_events[-1].get("event_hash") if prior_events else None,
        "prior_events": prior_events,
        "event": copy.deepcopy(event),
        "state_after": state,
        "command_record": _command_record(event),
        "pending_session": load_pending_session(output),
        "atlas_before": atlas_before,
        "atlas_after": atlas_after,
    }
    commit["commit_sha256"] = _commit_hash(commit)
    _atomic_write_json(output / RUNTIME_COMMIT_NAME, commit)
    return _apply_runtime_commit(output, commit)


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
