from __future__ import annotations

import copy
import hashlib
import html
import json
import random
import re
import secrets
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .blind_forge import (
    canonical_json,
    domain_hash,
    forge_blind_scenario,
    initial_player_state,
    resolve_session_action,
    reveal_session,
    scan_public_bundle_for_private_leaks,
    verify_session,
    write_blind_forge_session,
)
from .cosmic_possibility import (
    load_cosmic_possibility_registry,
    reasoned_candidate_matrix,
    registry_index,
)
from .generator import generate_system
from .bridge_visual_core import pin_start_package_for_save, resolve_start_package

FORGE_MODES = {"offline_base", "external_ai_assisted"}
SLOT_VERSION = "0.13.0"
PROPOSAL_SCHEMA = "axm.external-ai-forge-proposal.v1"
REQUEST_SCHEMA = "axm.external-ai-forge-request.v1"
SLOT_SCHEMA = "axm.adventure-save-slot.v1"

_ALLOWED_EMPHASIS = {
    "balanced",
    "chemistry_first",
    "physics_first",
    "falsification_first",
    "anomaly_hunting",
    "conservative",
}

_PROHIBITED_PROPOSAL_KEYS = {
    "origin_class",
    "private_simulation_truth",
    "resolution_secret",
    "stage_ceiling",
    "hidden_traits",
    "dominant_false_positive",
    "secondary_false_positive",
    "predetermined_outcome",
    "contact_result",
    "alien_identity",
}

_ALLOWED_PROPOSAL_KEYS = {
    "schema",
    "request_id",
    "proposal_author",
    "preferred_anomaly_family_ids",
    "preferred_life_architecture_ids",
    "emphasis_observable_ids",
    "investigation_emphasis",
    "rationale_summary",
    "proposal_nonce",
}


class AdventureSlotError(ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_slot_id(value: str) -> str:
    candidate = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-._")
    if not candidate:
        raise AdventureSlotError("slot id becomes empty after sanitization")
    if len(candidate) > 80:
        raise AdventureSlotError("slot id must be 80 characters or fewer")
    return candidate


def _slot_directory(slots_dir: Path, safe_id: str) -> Path:
    """Return one direct child of slots_dir and reject symlink/path escapes."""
    root = slots_dir.resolve()
    candidate = root / safe_id
    resolved = candidate.resolve()
    if resolved.parent != root:
        raise AdventureSlotError(f"slot path escapes the configured slots directory: {safe_id}")
    return candidate


def _walk_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key))
            keys.update(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_walk_keys(child))
    return keys


def _validate_string_list(value: Any, field: str, maximum: int = 12) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > maximum or any(not isinstance(item, str) for item in value):
        raise AdventureSlotError(f"{field} must be a list of at most {maximum} strings")
    return [item.strip() for item in value if item.strip()]


def validate_external_proposal(proposal: dict[str, Any], request: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(proposal, dict):
        raise AdventureSlotError("external proposal must be a JSON object")
    if proposal.get("schema") != PROPOSAL_SCHEMA:
        raise AdventureSlotError(f"external proposal schema must be {PROPOSAL_SCHEMA}")
    unknown = set(proposal) - _ALLOWED_PROPOSAL_KEYS
    if unknown:
        raise AdventureSlotError(f"unsupported proposal fields: {sorted(unknown)}")
    prohibited = _walk_keys(proposal) & _PROHIBITED_PROPOSAL_KEYS
    if prohibited:
        raise AdventureSlotError(
            "external AI may propose investigation lenses but may not directly choose hidden truth: "
            + ", ".join(sorted(prohibited))
        )
    author = str(proposal.get("proposal_author", "")).strip()
    if not author:
        raise AdventureSlotError("proposal_author is required")
    registry = load_cosmic_possibility_registry()
    indexes = registry_index(registry)
    anomaly_ids = _validate_string_list(proposal.get("preferred_anomaly_family_ids"), "preferred_anomaly_family_ids")
    architecture_ids = _validate_string_list(
        proposal.get("preferred_life_architecture_ids"), "preferred_life_architecture_ids"
    )
    observable_ids = _validate_string_list(proposal.get("emphasis_observable_ids"), "emphasis_observable_ids")
    unknown_anomalies = sorted(set(anomaly_ids) - set(indexes["anomalies"]))
    unknown_architectures = sorted(set(architecture_ids) - set(indexes["architectures"]))
    unknown_observables = sorted(set(observable_ids) - set(indexes["observables"]))
    if unknown_anomalies:
        raise AdventureSlotError(f"unknown anomaly family ids: {unknown_anomalies}")
    if unknown_architectures:
        raise AdventureSlotError(f"unknown life architecture ids: {unknown_architectures}")
    if unknown_observables:
        raise AdventureSlotError(f"unknown observable ids: {unknown_observables}")
    emphasis = str(proposal.get("investigation_emphasis", "balanced"))
    if emphasis not in _ALLOWED_EMPHASIS:
        raise AdventureSlotError(f"investigation_emphasis must be one of {sorted(_ALLOWED_EMPHASIS)}")
    rationale = _validate_string_list(proposal.get("rationale_summary"), "rationale_summary", maximum=8)
    if any(len(item) > 600 for item in rationale):
        raise AdventureSlotError("rationale_summary entries must be 600 characters or fewer")
    if request is not None:
        expected_request_id = request.get("request_id")
        supplied = proposal.get("request_id")
        if supplied and supplied != expected_request_id:
            raise AdventureSlotError("proposal request_id does not match this world/request")
        allowed_candidates = {item["candidate_id"] for item in request.get("candidate_shortlist", [])}
        allowed_anomalies = {item["anomaly_family_id"] for item in request.get("candidate_shortlist", [])}
        allowed_architectures = {item["life_architecture_id"] for item in request.get("candidate_shortlist", [])}
        if anomaly_ids and not set(anomaly_ids) & allowed_anomalies:
            raise AdventureSlotError("none of the preferred anomaly families occur in the local validated shortlist")
        if architecture_ids and not set(architecture_ids) & allowed_architectures:
            raise AdventureSlotError("none of the preferred life architectures occur in the local validated shortlist")
        if not allowed_candidates:
            raise AdventureSlotError("external request has no validated candidate shortlist")
    normalized = {
        "schema": PROPOSAL_SCHEMA,
        "request_id": proposal.get("request_id"),
        "proposal_author": author,
        "preferred_anomaly_family_ids": anomaly_ids,
        "preferred_life_architecture_ids": architecture_ids,
        "emphasis_observable_ids": observable_ids,
        "investigation_emphasis": emphasis,
        "rationale_summary": rationale,
        "proposal_nonce": str(proposal.get("proposal_nonce", "")),
    }
    normalized["proposal_sha256"] = domain_hash(normalized, "AXM-EXTERNAL-AI-FORGE-PROPOSAL-V1")
    return normalized


def prepare_external_forge_request_data(system: dict[str, Any], forge_seed: str) -> dict[str, Any]:
    request_seed = f"{forge_seed}|EXTERNAL-REQUEST-V1"
    matrix = reasoned_candidate_matrix(system, request_seed)
    indexes = registry_index()
    shortlist = []
    for candidate in matrix["shortlist"]:
        anomaly = indexes["anomalies"][candidate["anomaly_family_id"]]
        architecture = indexes["architectures"][candidate["life_architecture_id"]]
        shortlist.append(
            {
                "candidate_id": candidate["candidate_id"],
                "anomaly_family_id": candidate["anomaly_family_id"],
                "anomaly_name": anomaly.get("name", candidate["anomaly_family_id"]),
                "life_architecture_id": candidate["life_architecture_id"],
                "life_architecture_name": architecture.get("name", candidate["life_architecture_id"]),
                "local_constraint_score": candidate["score"],
                "claim_ceiling": candidate["claim_ceiling"],
                "observable_channels": sorted(
                    set(anomaly.get("observables", [])) | set(architecture.get("observables", []))
                ),
                "false_positive_control_count": len(anomaly.get("controls", [])),
                "source_ids": candidate["source_ids"],
            }
        )
    request_core = {
        "schema": REQUEST_SCHEMA,
        "forge_version": SLOT_VERSION,
        "system_id": system.get("system_id"),
        "system_name": system.get("name"),
        "public_environment": matrix["environment"],
        "candidate_shortlist": shortlist,
        "allowed_investigation_emphasis": sorted(_ALLOWED_EMPHASIS),
        "allowed_observable_ids": [item["id"] for item in load_cosmic_possibility_registry()["agnostic_observables"]],
        "external_ai_task": [
            "Propose investigation lenses, not a guaranteed story.",
            "Do not choose whether life, intelligence, contact, or new physics is actually present.",
            "Prefer candidates with measurable observables and strong false-positive controls.",
            "Return only the proposal schema shown in proposal_template.",
        ],
        "proposal_template": {
            "schema": PROPOSAL_SCHEMA,
            "request_id": None,
            "proposal_author": "external model or human reasoning seat",
            "preferred_anomaly_family_ids": [],
            "preferred_life_architecture_ids": [],
            "emphasis_observable_ids": [],
            "investigation_emphasis": "balanced",
            "rationale_summary": [],
            "proposal_nonce": "",
        },
    }
    request_id = domain_hash(request_core, "AXM-EXTERNAL-AI-FORGE-REQUEST-V1")
    request_core["request_id"] = request_id
    request_core["proposal_template"]["request_id"] = request_id
    return request_core


def prepare_external_forge_request(world_seed: str, forge_seed: str, output: Path) -> dict[str, Any]:
    system = generate_system(world_seed).to_dict()
    request = prepare_external_forge_request_data(system, forge_seed)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(request, indent=2, ensure_ascii=False), encoding="utf-8")
    return request


def _candidate_selected_score(private_payload: dict[str, Any]) -> float:
    selected = private_payload["reasoned_candidate_matrix"]["selected_candidate_id"]
    for row in private_payload["reasoned_candidate_matrix"]["shortlist"]:
        if row["candidate_id"] == selected:
            return float(row["score"])
    return 0.0


def _rebind_private_candidate(
    system: dict[str, Any],
    private_payload: dict[str, Any],
    public_bundle: dict[str, Any],
    selected_candidate_id: str,
    forge_author: str,
    forge_input_receipt: dict[str, Any],
    secret_seed_material: str,
    public_mode: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    private_payload = copy.deepcopy(private_payload)
    public_bundle = copy.deepcopy(public_bundle)
    matrix = private_payload["reasoned_candidate_matrix"]
    selected = next(
        (row for row in matrix["shortlist"] if row["candidate_id"] == selected_candidate_id),
        None,
    )
    if selected is None:
        raise AdventureSlotError("selected candidate is outside the locally validated shortlist")
    indexes = registry_index()
    anomaly = copy.deepcopy(indexes["anomalies"][selected["anomaly_family_id"]])
    architecture = copy.deepcopy(indexes["architectures"][selected["life_architecture_id"]])
    controls = anomaly.get("controls", []) or ["unmodeled natural process"]
    rng = random.Random(
        int.from_bytes(
            hashlib.sha256(
                f"{secret_seed_material}|{system.get('system_id')}|{selected_candidate_id}".encode("utf-8")
            ).digest()[:16],
            "big",
        )
    )
    matrix["selected_candidate_id"] = selected_candidate_id
    matrix["selection_receipt"] = domain_hash(
        {
            "system_id": system.get("system_id"),
            "selected_candidate_id": selected_candidate_id,
            "forge_input_receipt": forge_input_receipt,
        },
        "AXM-BLIND-CANDIDATE-REBIND-V1",
    )
    private_payload["forge_version"] = SLOT_VERSION
    private_payload["forge_author"] = forge_author
    private_payload["selected_anomaly_family"] = anomaly
    private_payload["selected_life_architecture"] = architecture
    private_payload["private_simulation_truth"]["dominant_false_positive"] = rng.choice(controls)
    private_payload["private_simulation_truth"]["secondary_false_positive"] = rng.choice(controls)
    private_payload["private_simulation_truth"]["resolution_secret"] = hashlib.sha256(
        f"AXM-SLOT-RESOLUTION|{secret_seed_material}|{system.get('system_id')}|{rng.random()}".encode("utf-8")
    ).hexdigest()
    private_payload["test_plan"] = {
        "required_controls": anomaly.get("controls", []),
        "required_questions": architecture.get("required_questions", []),
        "eligible_observables": sorted(
            set(anomaly.get("observables", [])) | set(architecture.get("observables", []))
        ),
        "claim_ceiling": architecture.get("claim_ceiling"),
    }
    private_payload["source_ids"] = selected["source_ids"]
    private_payload["forge_input_receipt"] = forge_input_receipt

    commitment = domain_hash(private_payload, "AXM-BLIND-FORGE-COMMITMENT-V1")
    public_bundle["forge_version"] = SLOT_VERSION
    public_bundle["private_scenario_commitment_sha256"] = commitment
    public_bundle["initial_state"] = initial_player_state(commitment)
    public_bundle["source_ids"] = selected["source_ids"]
    public_bundle["adventure_slot_start"] = {
        "forge_mode": public_mode,
        "offline_play_after_creation": True,
        "external_connection_required_after_creation": False,
        "private_seed_vault_included_in_player_bundle": False,
        "local_runtime_is_authoritative": True,
    }
    public_bundle["blindness_contract"]["offline_runtime_can_resolve_every_turn"] = True
    public_bundle["blindness_contract"]["external_ai_connection_required_during_play"] = False
    leaks = scan_public_bundle_for_private_leaks(public_bundle, private_payload)
    if leaks:
        raise AdventureSlotError(f"public bundle leaked private values after slot assembly: {leaks}")
    return private_payload, public_bundle


def forge_offline_base_scenario(
    system: dict[str, Any],
    forge_seed: str,
    passes: int = 7,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if passes < 3 or passes > 15:
        raise AdventureSlotError("offline forge passes must be between 3 and 15")
    results: list[tuple[dict[str, Any], dict[str, Any]]] = []
    vote_rows: list[dict[str, Any]] = []
    for index in range(passes):
        pass_seed = f"{forge_seed}|OFFLINE-REASONING-LENS-{index:02d}"
        private_payload, public_bundle = forge_blind_scenario(
            system,
            pass_seed,
            forge_author=f"AXM offline possibility forge lens {index + 1}/{passes}",
        )
        selected = private_payload["reasoned_candidate_matrix"]["selected_candidate_id"]
        score = _candidate_selected_score(private_payload)
        vote_rows.append(
            {
                "lens": index,
                "selected_candidate_id": selected,
                "constraint_score": score,
                "pass_receipt": hashlib.sha256(pass_seed.encode("utf-8")).hexdigest(),
            }
        )
        results.append((private_payload, public_bundle))
    candidate_ids = sorted({row["selected_candidate_id"] for row in vote_rows})
    ranked = []
    for candidate_id in candidate_ids:
        rows = [row for row in vote_rows if row["selected_candidate_id"] == candidate_id]
        ranked.append(
            {
                "candidate_id": candidate_id,
                "votes": len(rows),
                "mean_constraint_score": sum(row["constraint_score"] for row in rows) / len(rows),
                "tie_break": hashlib.sha256(f"{forge_seed}|{candidate_id}".encode("utf-8")).hexdigest(),
            }
        )
    ranked.sort(
        key=lambda row: (-row["votes"], -row["mean_constraint_score"], row["tie_break"])
    )
    winner = ranked[0]["candidate_id"]
    base_index = next(
        index
        for index, (private_payload, _public_bundle) in enumerate(results)
        if private_payload["reasoned_candidate_matrix"]["selected_candidate_id"] == winner
    )
    receipt = {
        "mode": "offline_base",
        "offline_reasoning_passes": passes,
        "external_model_used": False,
        "candidate_votes": vote_rows,
        "ranking": ranked,
        "selected_candidate_id": winner,
        "policy": (
            "Multiple deterministic constraint lenses nominate scientifically bounded candidates. "
            "The local forge seals one winner before play; no external model is required."
        ),
    }
    return _rebind_private_candidate(
        system,
        results[base_index][0],
        results[base_index][1],
        winner,
        forge_author="AXM seven-pass offline possibility forge",
        forge_input_receipt=receipt,
        secret_seed_material=f"{forge_seed}|OFFLINE-COUNCIL",
        public_mode="offline_base",
    )


def _choose_external_candidate(
    private_payload: dict[str, Any],
    proposal: dict[str, Any],
) -> str:
    indexes = registry_index()
    anomaly_preferences = set(proposal["preferred_anomaly_family_ids"])
    architecture_preferences = set(proposal["preferred_life_architecture_ids"])
    emphasis_observables = set(proposal["emphasis_observable_ids"])
    emphasis = proposal["investigation_emphasis"]
    rows = []
    for candidate in private_payload["reasoned_candidate_matrix"]["shortlist"]:
        anomaly = indexes["anomalies"][candidate["anomaly_family_id"]]
        architecture = indexes["architectures"][candidate["life_architecture_id"]]
        observable_text = {
            str(item).lower().replace(" ", "_")
            for item in anomaly.get("observables", []) + architecture.get("observables", [])
        }
        score = float(candidate["score"])
        if candidate["anomaly_family_id"] in anomaly_preferences:
            score += 0.14
        if candidate["life_architecture_id"] in architecture_preferences:
            score += 0.14
        score += min(0.08, 0.025 * len(observable_text & emphasis_observables))
        if emphasis == "falsification_first":
            score += min(0.08, 0.02 * len(anomaly.get("controls", [])))
        elif emphasis == "anomaly_hunting":
            score += min(0.06, 0.01 * len(anomaly.get("observables", [])))
        elif emphasis == "chemistry_first" and any(
            token in observable_text for token in {"chemical_complexity", "molecular_diversity", "disequilibrium"}
        ):
            score += 0.06
        elif emphasis == "physics_first" and candidate["anomaly_family_id"] in {
            "rare_morphology",
            "expansion_rate_disagreement",
            "gravitational_mass_mismatch",
        }:
            score += 0.06
        elif emphasis == "conservative":
            score += min(0.06, 0.015 * len(anomaly.get("controls", [])))
        tie_break = hashlib.sha256(
            f"{proposal['proposal_sha256']}|{candidate['candidate_id']}".encode("utf-8")
        ).hexdigest()
        rows.append((score, tie_break, candidate["candidate_id"]))
    rows.sort(key=lambda row: (-row[0], row[1]))
    return rows[0][2]


def forge_external_ai_assisted_scenario(
    system: dict[str, Any],
    forge_seed: str,
    proposal: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    request = prepare_external_forge_request_data(system, forge_seed)
    proposal = validate_external_proposal(proposal, request=request)
    request_seed = f"{forge_seed}|EXTERNAL-REQUEST-V1"
    private_payload, public_bundle = forge_blind_scenario(
        system,
        request_seed,
        forge_author="Local validator preparing an externally proposed investigation lens",
    )
    selected_candidate_id = _choose_external_candidate(private_payload, proposal)
    receipt = {
        "mode": "external_ai_assisted",
        "request_id": request["request_id"],
        "proposal": proposal,
        "local_shortlist_size": len(private_payload["reasoned_candidate_matrix"]["shortlist"]),
        "selected_candidate_id": selected_candidate_id,
        "external_ai_role": "proposal only",
        "local_runtime_role": "validation, hidden-state sealing, commitment, event resolution, and replay",
        "external_connection_required_after_creation": False,
    }
    return _rebind_private_candidate(
        system,
        private_payload,
        public_bundle,
        selected_candidate_id,
        forge_author=f"External proposal by {proposal['proposal_author']} validated and sealed locally",
        forge_input_receipt=receipt,
        secret_seed_material=f"{forge_seed}|{proposal['proposal_sha256']}",
        public_mode="external_ai_assisted",
    )


def _slot_console(metadata: dict[str, Any], public_bundle: dict[str, Any], state: dict[str, Any]) -> str:
    actions = "".join(
        f"<li><code>{html.escape(action['id'])}</code><span>{html.escape(action['name'])}</span></li>"
        for action in public_bundle["available_actions"]
    )
    mode_name = (
        "Seven-pass offline forge"
        if metadata["forge_mode"] == "offline_base"
        else "External proposal, locally validated and sealed"
    )
    payload = json.dumps(
        {"metadata": metadata, "state": state, "public_bundle": public_bundle},
        ensure_ascii=False,
    ).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{html.escape(metadata['display_name'])}</title>
<style>
:root{{color-scheme:dark;--bg:#071017;--panel:#0e1a23;--line:#294654;--text:#eff8fb;--muted:#9eb4bc;--accent:#83e1d2}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at top,#17323e,var(--bg) 42%);color:var(--text);font-family:system-ui,sans-serif}}
main{{max-width:1040px;margin:auto;padding:24px}}header{{border-bottom:1px solid var(--line);padding-bottom:18px}}
.eyebrow{{color:var(--accent);text-transform:uppercase;letter-spacing:.15em;font-size:.8rem}}
h1{{margin:.35rem 0;font-size:clamp(1.7rem,4vw,3rem)}}p,span{{color:var(--muted)}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px;margin:18px 0}}
.card{{background:rgba(14,26,35,.9);border:1px solid var(--line);border-radius:16px;padding:16px}}.value{{font-size:1.55rem;color:var(--accent)}}
.notice{{border:1px dashed var(--accent);border-radius:13px;padding:14px}}ul{{list-style:none;padding:0;display:grid;gap:8px}}li{{display:grid;gap:4px;border-left:3px solid var(--line);padding:8px 10px}}code{{color:#bdf6ec;overflow-wrap:anywhere}}
</style></head><body><main>
<header><div class='eyebrow'>Persistent adventure save slot</div><h1>{html.escape(metadata['display_name'])}</h1><p>{html.escape(metadata['system_name'])}</p></header>
<section class='grid'>
<div class='card'><div class='eyebrow'>Start mode</div><div class='value'>{html.escape(mode_name)}</div></div>
<div class='card'><div class='eyebrow'>Turn</div><div class='value'>{state['turn']}</div><p>{html.escape(state['status'])}</p></div>
<div class='card'><div class='eyebrow'>Evidence stage</div><div class='value'>{state['evidence_stage']}</div><p>{html.escape(state['claim_ceiling'])}</p></div>
<div class='card'><div class='eyebrow'>Offline guarantee</div><div class='value'>Always available</div><p>No external AI connection is required after slot creation.</p></div>
</section>
<section class='card'><h2>Slot rule</h2><div class='notice'>The starting hidden scenario is sealed before play. Human and machine explorers receive the same public evidence interface. External AI is optional and may only propose a lens; the local forge validates, seals, runs, saves, and replays the expedition.</div></section>
<section class='card'><h2>Available first actions</h2><ul>{actions}</ul></section>
<section class='card'><h2>Commitment</h2><code>{public_bundle['private_scenario_commitment_sha256']}</code></section>
<script type='application/json' id='axm-slot-public-state'>{payload}</script>
</main></body></html>"""


def _manifest_files(slot_dir: Path) -> dict[str, dict[str, Any]]:
    files: dict[str, dict[str, Any]] = {}
    for path in sorted(slot_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(slot_dir).as_posix()
        if relative == "SLOT_MANIFEST.json":
            continue
        files[relative] = {"bytes": path.stat().st_size, "sha256": _sha256_file(path)}
    return files


def refresh_slot_manifest(slot_dir: Path) -> dict[str, Any]:
    metadata = json.loads((slot_dir / "SLOT_METADATA.json").read_text(encoding="utf-8"))
    manifest = {
        "schema": "axm.adventure-slot-manifest.v1",
        "slot_id": metadata["slot_id"],
        "slot_version": metadata["slot_version"],
        "generated_at": _utc_now(),
        "managed_file_count": 0,
        "files": {},
    }
    manifest["files"] = _manifest_files(slot_dir)
    manifest["managed_file_count"] = len(manifest["files"])
    (slot_dir / "SLOT_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest


def create_adventure_slot(
    slots_dir: Path,
    slot_id: str,
    display_name: str,
    world_seed: str,
    forge_seed: str,
    forge_mode: str = "offline_base",
    proposal: dict[str, Any] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    if forge_mode not in FORGE_MODES:
        raise AdventureSlotError(f"forge_mode must be one of {sorted(FORGE_MODES)}")
    safe_id = _safe_slot_id(slot_id)
    slot_dir = _slot_directory(slots_dir, safe_id)
    if slot_dir.exists():
        if not overwrite:
            raise AdventureSlotError(f"slot already exists: {safe_id}")
        shutil.rmtree(slot_dir)
    slot_dir.mkdir(parents=True)
    session_dir = slot_dir / "session"
    private_slot_dir = slot_dir / "slot_private"
    private_slot_dir.mkdir(parents=True)

    system = generate_system(world_seed).to_dict()
    if forge_mode == "offline_base":
        private_payload, public_bundle = forge_offline_base_scenario(system, forge_seed)
    else:
        if proposal is None:
            raise AdventureSlotError("external_ai_assisted mode requires a proposal JSON file")
        private_payload, public_bundle = forge_external_ai_assisted_scenario(system, forge_seed, proposal)

    paths = write_blind_forge_session(session_dir, system, private_payload, public_bundle)
    ship_start_pin = pin_start_package_for_save(resolve_start_package())
    created_at = _utc_now()
    metadata = {
        "schema": SLOT_SCHEMA,
        "slot_version": SLOT_VERSION,
        "slot_id": safe_id,
        "display_name": display_name.strip() or safe_id,
        "created_at": created_at,
        "updated_at": created_at,
        "forge_mode": forge_mode,
        "offline_base_available": True,
        "external_connection_required_after_creation": False,
        "human_player_supported": True,
        "machine_player_supported": True,
        "collaborative_player_supported": True,
        "system_id": system["system_id"],
        "system_name": system["name"],
        "ship_blueprint_id": ship_start_pin["ship_blueprint_id"],
        "ship_blueprint_version": ship_start_pin["ship_blueprint_version"],
        "ship_blueprint_commitment": ship_start_pin["ship_blueprint_commitment"],
        "interior_archetype_id": ship_start_pin["interior_archetype_id"],
        "crew_start_id": ship_start_pin["crew_start_id"],
        "private_scenario_commitment_sha256": paths["commitment"],
        "status": "active",
        "turn": 0,
        "evidence_stage": 0,
        "session_directory": "session",
        "player_public_directory": "session/player_public",
    }
    start_receipt = {
        "schema": "axm.adventure-slot-private-start-receipt.v1",
        "slot_id": safe_id,
        "world_seed": world_seed,
        "forge_seed": forge_seed,
        "forge_mode": forge_mode,
        "proposal": proposal if forge_mode == "external_ai_assisted" else None,
        "system_id": system["system_id"],
        "commitment": paths["commitment"],
        "ship_start_pin_receipt": ship_start_pin["pin_receipt"],
        "created_at": created_at,
        "warning": "Keep slot_private and session/forge_private away from a blind explorer.",
    }
    (slot_dir / "SLOT_METADATA.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (slot_dir / "SHIP_START_PIN.json").write_text(
        json.dumps(ship_start_pin, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (private_slot_dir / "START_RECEIPT.json").write_text(
        json.dumps(start_receipt, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    player_handoff = (
        "AXM ADVENTURE SAVE SLOT\n\n"
        f"Slot: {metadata['display_name']}\n"
        f"Forge mode: {forge_mode}\n\n"
        "The expedition is fully playable offline after creation.\n"
        "Give session/player_public to a blind human or machine explorer.\n"
        "Keep slot_private and session/forge_private hidden until the chosen reveal point.\n"
        "The built-in offline forge is always available for new slots.\n"
        f"Pinned ship blueprint: {ship_start_pin['ship_blueprint_id']} v{ship_start_pin['ship_blueprint_version']}\n"
    )
    (slot_dir / "SLOT_HANDOFF.txt").write_text(player_handoff, encoding="utf-8")
    state = public_bundle["initial_state"]
    (slot_dir / "slot_console.html").write_text(
        _slot_console(metadata, public_bundle, state), encoding="utf-8"
    )
    manifest = refresh_slot_manifest(slot_dir)
    return {
        "slot_dir": slot_dir,
        "metadata": metadata,
        "manifest": manifest,
        "player_console": session_dir / "player_public" / "player_console.html",
        "slot_console": slot_dir / "slot_console.html",
    }


def _load_slot(slots_dir: Path, slot_id: str) -> tuple[Path, dict[str, Any], Path]:
    slot_dir = _slot_directory(slots_dir, _safe_slot_id(slot_id))
    metadata_path = slot_dir / "SLOT_METADATA.json"
    if not metadata_path.exists():
        raise AdventureSlotError(f"slot not found: {slot_id}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    session_dir = slot_dir / metadata.get("session_directory", "session")
    return slot_dir, metadata, session_dir


def act_in_adventure_slot(
    slots_dir: Path,
    slot_id: str,
    action_id: str,
    entropy_token: str | None = None,
) -> dict[str, Any]:
    slot_dir, metadata, session_dir = _load_slot(slots_dir, slot_id)
    token = entropy_token or secrets.token_hex(32)
    result = resolve_session_action(session_dir, action_id, token)
    state = result["state"]
    metadata["updated_at"] = _utc_now()
    metadata["turn"] = state["turn"]
    metadata["evidence_stage"] = state["evidence_stage"]
    metadata["status"] = state["status"]
    (slot_dir / "SLOT_METADATA.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    public_bundle = json.loads(
        (session_dir / "player_public" / "mission_bundle.json").read_text(encoding="utf-8")
    )
    (slot_dir / "slot_console.html").write_text(
        _slot_console(metadata, public_bundle, state), encoding="utf-8"
    )
    manifest = refresh_slot_manifest(slot_dir)
    return {
        "event": result["event"],
        "state": state,
        "metadata": metadata,
        "manifest": manifest,
        "entropy_token_stored_privately": True,
    }


def verify_adventure_slot(slots_dir: Path, slot_id: str) -> dict[str, Any]:
    slot_dir, metadata, session_dir = _load_slot(slots_dir, slot_id)
    manifest = json.loads((slot_dir / "SLOT_MANIFEST.json").read_text(encoding="utf-8"))
    manifest_failures = []
    current = _manifest_files(slot_dir)
    expected = manifest.get("files", {})
    for relative in sorted(set(current) | set(expected)):
        if relative not in expected:
            manifest_failures.append({"file": relative, "error": "unexpected"})
        elif relative not in current:
            manifest_failures.append({"file": relative, "error": "missing"})
        elif current[relative] != expected[relative]:
            manifest_failures.append(
                {"file": relative, "error": "hash_or_size_mismatch", "expected": expected[relative], "actual": current[relative]}
            )
    private_payload = json.loads(
        (session_dir / "forge_private" / "hidden_scenario.json").read_text(encoding="utf-8")
    )
    public_bundle = json.loads(
        (session_dir / "player_public" / "mission_bundle.json").read_text(encoding="utf-8")
    )
    events = [
        json.loads(line)
        for line in (session_dir / "player_public" / "event_ledger.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    tokens = json.loads(
        (session_dir / "forge_private" / "ENTROPY_TOKENS.json").read_text(encoding="utf-8")
    )
    session_result = verify_session(private_payload, public_bundle, events, tokens)
    state = json.loads(
        (session_dir / "player_public" / "player_state.json").read_text(encoding="utf-8")
    )
    state_matches = session_result.get("valid") and session_result.get("final_state") == state
    start_pin_path = slot_dir / "SHIP_START_PIN.json"
    start_pin_valid = False
    if start_pin_path.exists():
        try:
            stored_pin = json.loads(start_pin_path.read_text(encoding="utf-8"))
            expected_pin = pin_start_package_for_save(resolve_start_package(
                bridge_archetype_id=stored_pin.get("bridge_archetype_id"),
                timeline_start_id=stored_pin.get("timeline_start_id"),
                crew_start_id=stored_pin.get("crew_start_id"),
                render_profile_id=stored_pin.get("initial_render_profile_id", "axm.render.paint-foundation.v1"),
                interior_archetype_id=stored_pin.get("interior_archetype_id"),
                ship_blueprint_id=stored_pin.get("ship_blueprint_id"),
            ))
            start_pin_valid = stored_pin == expected_pin
        except Exception:
            start_pin_valid = False
    metadata_matches = (
        metadata.get("private_scenario_commitment_sha256")
        == public_bundle.get("private_scenario_commitment_sha256")
        and metadata.get("turn") == state.get("turn")
        and metadata.get("evidence_stage") == state.get("evidence_stage")
        and metadata.get("external_connection_required_after_creation") is False
        and metadata.get("offline_base_available") is True
        and metadata.get("ship_blueprint_id") == (stored_pin.get("ship_blueprint_id") if start_pin_path.exists() and start_pin_valid else None)
        and metadata.get("ship_blueprint_commitment") == (stored_pin.get("ship_blueprint_commitment") if start_pin_path.exists() and start_pin_valid else None)
    )
    valid = not manifest_failures and bool(session_result.get("valid")) and state_matches and metadata_matches and start_pin_valid
    return {
        "schema": "axm.adventure-slot-verification.v1",
        "slot_id": metadata["slot_id"],
        "valid": valid,
        "manifest_valid": not manifest_failures,
        "manifest_failures": manifest_failures,
        "session": session_result,
        "state_matches_replay": state_matches,
        "metadata_matches_public_state": metadata_matches,
        "ship_start_pin_valid": start_pin_valid,
        "events": len(events),
    }


def reveal_adventure_slot(slots_dir: Path, slot_id: str) -> dict[str, Any]:
    slot_dir, metadata, session_dir = _load_slot(slots_dir, slot_id)
    result = reveal_session(session_dir)
    metadata["updated_at"] = _utc_now()
    metadata["revealed"] = bool(result.get("valid"))
    (slot_dir / "SLOT_METADATA.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    public_bundle = json.loads(
        (session_dir / "player_public" / "mission_bundle.json").read_text(encoding="utf-8")
    )
    state = json.loads(
        (session_dir / "player_public" / "player_state.json").read_text(encoding="utf-8")
    )
    (slot_dir / "slot_console.html").write_text(
        _slot_console(metadata, public_bundle, state), encoding="utf-8"
    )
    refresh_slot_manifest(slot_dir)
    return result


def export_player_bundle(slots_dir: Path, slot_id: str, output_zip: Path | None = None) -> Path:
    slot_dir, metadata, session_dir = _load_slot(slots_dir, slot_id)
    public_dir = session_dir / "player_public"
    exports = slot_dir / "exports"
    exports.mkdir(exist_ok=True)
    output_zip = output_zip or exports / f"{metadata['slot_id']}_BLIND_PLAYER_BUNDLE.zip"
    public_info = {
        "schema": "axm.adventure-slot-public-export.v1",
        "slot_id": metadata["slot_id"],
        "display_name": metadata["display_name"],
        "system_id": metadata["system_id"],
        "system_name": metadata["system_name"],
        "forge_mode": metadata["forge_mode"],
        "ship_blueprint_id": metadata.get("ship_blueprint_id"),
        "ship_blueprint_version": metadata.get("ship_blueprint_version"),
        "interior_archetype_id": metadata.get("interior_archetype_id"),
        "external_connection_required": False,
        "private_files_included": False,
    }
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("SLOT_PUBLIC_INFO.json", json.dumps(public_info, indent=2, ensure_ascii=False))
        for path in sorted(public_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(public_dir).as_posix())
    with zipfile.ZipFile(output_zip) as archive:
        names = archive.namelist()
        if any("private" in name.lower() for name in names):
            raise AdventureSlotError("player export unexpectedly contains a private path")
        for name in names:
            if name.endswith((".json", ".jsonl", ".txt", ".html")):
                text = archive.read(name).decode("utf-8", errors="replace")
                if "resolution_secret" in text or "private_simulation_truth" in text:
                    raise AdventureSlotError(f"player export leaked private material in {name}")
    refresh_slot_manifest(slot_dir)
    return output_zip


def list_adventure_slots(slots_dir: Path) -> list[dict[str, Any]]:
    if not slots_dir.exists():
        return []
    rows = []
    for metadata_path in sorted(slots_dir.glob("*/SLOT_METADATA.json")):
        try:
            _slot_directory(slots_dir, _safe_slot_id(metadata_path.parent.name))
            rows.append(json.loads(metadata_path.read_text(encoding="utf-8")))
        except (AdventureSlotError, OSError, json.JSONDecodeError):
            continue
    return rows
