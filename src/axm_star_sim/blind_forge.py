from __future__ import annotations

import copy
import hashlib
import json
import random
from pathlib import Path
from typing import Any

from .cosmic_possibility import (
    load_cosmic_possibility_registry,
    reasoned_candidate_matrix,
    registry_index,
    system_environment,
)


class BlindForgeError(ValueError):
    pass


ACTION_CATALOG: list[dict[str, Any]] = [
    {
        "id": "broad_spectrum_survey",
        "name": "Run a broad-spectrum survey",
        "channel": "general_pattern",
        "sensitivity": 0.55,
        "independence": 0.25,
        "cost_hours": 6.0,
        "description": "Look for unusual structure without assuming a particular chemistry or organism.",
    },
    {
        "id": "repeat_changed_geometry",
        "name": "Repeat from a changed geometry",
        "channel": "repeatability",
        "sensitivity": 0.68,
        "independence": 0.65,
        "cost_hours": 12.0,
        "description": "Test whether the pattern survives orbital phase, pointing, and viewing-angle changes.",
    },
    {
        "id": "switch_instrument_family",
        "name": "Use an independent instrument family",
        "channel": "independent_replication",
        "sensitivity": 0.72,
        "independence": 0.92,
        "cost_hours": 10.0,
        "description": "Check the candidate with different hardware and processing assumptions.",
    },
    {
        "id": "measure_chemical_complexity",
        "name": "Measure molecular diversity and complexity",
        "channel": "chemical_complexity",
        "sensitivity": 0.78,
        "independence": 0.72,
        "cost_hours": 18.0,
        "description": "Test statistical organization rather than searching only for Earth-specific molecules.",
    },
    {
        "id": "map_energy_gradients",
        "name": "Map persistent energy-transfer gradients",
        "channel": "energy_transfer",
        "sensitivity": 0.75,
        "independence": 0.70,
        "cost_hours": 16.0,
        "description": "Look for maintained redox, electrochemical, or thermal organization.",
    },
    {
        "id": "search_compartments",
        "name": "Search for bounded compartments",
        "channel": "elemental_compartmentalization",
        "sensitivity": 0.74,
        "independence": 0.68,
        "cost_hours": 20.0,
        "description": "Search for repeated bounded regions that concentrate selected elements or molecules.",
    },
    {
        "id": "stress_response_test",
        "name": "Apply a reversible environmental perturbation",
        "channel": "adaptive_response",
        "sensitivity": 0.70,
        "independence": 0.66,
        "cost_hours": 14.0,
        "description": "Test whether the system shows retained, context-dependent response without assuming intent.",
    },
    {
        "id": "abiotic_control_campaign",
        "name": "Run abiotic and instrumental controls",
        "channel": "false_positive_control",
        "sensitivity": 0.82,
        "independence": 0.90,
        "cost_hours": 22.0,
        "description": "Attempt to reproduce the signal through known physics, chemistry, contamination, and processing artifacts.",
    },
    {
        "id": "independent_blind_reanalysis",
        "name": "Commission a blind independent reanalysis",
        "channel": "independent_replication",
        "sensitivity": 0.86,
        "independence": 1.0,
        "cost_hours": 30.0,
        "description": "Give another analysis seat the raw data without the favored hypothesis.",
    },
    {
        "id": "move_on_preserve_candidate",
        "name": "Archive the candidate and continue exploring",
        "channel": "mission_continuation",
        "sensitivity": 0.0,
        "independence": 0.0,
        "cost_hours": 2.0,
        "description": "Preserve all evidence without forcing a conclusion.",
    },
]

ORIGIN_PRIORS = [
    ("instrumental_or_processing", 0.15),
    ("known_abiotic_physics", 0.28),
    ("unmodeled_abiotic_complexity", 0.18),
    ("prebiotic_organized_chemistry", 0.16),
    ("life_like_but_unresolved", 0.11),
    ("candidate_living_system", 0.07),
    ("novel_physics_unresolved", 0.05),
]


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def domain_hash(value: Any, domain: str) -> str:
    return hashlib.sha256((domain + "\n" + canonical_json(value)).encode("utf-8")).hexdigest()


def _rng(*parts: str) -> random.Random:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:16], "big"))


def _weighted_pick(rng: random.Random, choices: list[tuple[str, float]]) -> str:
    roll = rng.random() * sum(weight for _, weight in choices)
    cursor = 0.0
    for value, weight in choices:
        cursor += weight
        if roll <= cursor:
            return value
    return choices[-1][0]


def _hidden_traits(origin: str, rng: random.Random) -> dict[str, float]:
    baselines = {
        "instrumental_or_processing": (0.18, 0.08, 0.04, 0.02, 0.12, 0.04),
        "known_abiotic_physics": (0.58, 0.35, 0.22, 0.05, 0.30, 0.12),
        "unmodeled_abiotic_complexity": (0.70, 0.56, 0.45, 0.18, 0.50, 0.25),
        "prebiotic_organized_chemistry": (0.76, 0.67, 0.62, 0.38, 0.56, 0.45),
        "life_like_but_unresolved": (0.85, 0.78, 0.75, 0.58, 0.72, 0.63),
        "candidate_living_system": (0.92, 0.88, 0.86, 0.78, 0.84, 0.80),
        "novel_physics_unresolved": (0.74, 0.62, 0.40, 0.20, 0.66, 0.30),
    }
    keys = [
        "persistence",
        "energy_organization",
        "compartmentalization",
        "adaptive_memory",
        "chemical_complexity",
        "replication_like_recurrence",
    ]
    values = baselines[origin]
    return {key: round(min(1.0, max(0.0, base + rng.uniform(-0.09, 0.09))), 6) for key, base in zip(keys, values)}


def _stage_ceiling_for_origin(origin: str) -> int:
    return {
        "instrumental_or_processing": 2,
        "known_abiotic_physics": 3,
        "unmodeled_abiotic_complexity": 4,
        "prebiotic_organized_chemistry": 5,
        "life_like_but_unresolved": 5,
        "candidate_living_system": 7,
        "novel_physics_unresolved": 4,
    }[origin]


def forge_blind_scenario(
    system: dict[str, Any],
    forge_seed: str,
    forge_author: str = "Axiom/Mir seed-forge reasoning",
) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = load_cosmic_possibility_registry()
    matrix = reasoned_candidate_matrix(system, forge_seed, registry)
    indexes = registry_index(registry)
    selected = next(item for item in matrix["shortlist"] if item["candidate_id"] == matrix["selected_candidate_id"])
    anomaly = indexes["anomalies"][selected["anomaly_family_id"]]
    architecture = indexes["architectures"][selected["life_architecture_id"]]
    rng = _rng(forge_seed, system.get("system_id", ""), "hidden-scenario")
    origin = _weighted_pick(rng, ORIGIN_PRIORS)
    traits = _hidden_traits(origin, rng)
    false_positive = rng.choice(anomaly.get("controls", ["unmodeled natural process"]))
    secondary_false_positive = rng.choice(anomaly.get("controls", [false_positive]))
    resolution_secret = hashlib.sha256(
        f"AXM-BLIND-RESOLUTION|{forge_seed}|{system.get('system_id')}|{rng.random()}".encode("utf-8")
    ).hexdigest()
    private_payload = {
        "schema": "axm.blind-forge-private-scenario.v1",
        "forge_version": "0.8.0",
        "forge_author": forge_author,
        "system_id": system.get("system_id"),
        "environment": system_environment(system),
        "reasoned_candidate_matrix": matrix,
        "selected_anomaly_family": anomaly,
        "selected_life_architecture": architecture,
        "private_simulation_truth": {
            "truth_type": "private_simulation_state",
            "origin_class": origin,
            "stage_ceiling": _stage_ceiling_for_origin(origin),
            "traits": traits,
            "dominant_false_positive": false_positive,
            "secondary_false_positive": secondary_false_positive,
            "resolution_secret": resolution_secret,
            "future_is_open": True,
            "future_rule": (
                "The private packet fixes a hidden starting phenomenon. Player actions, measurement limits, ship state, "
                "and runtime entropy still determine which evidence becomes available and what consequences follow."
            ),
            "real_world_claim": "None. This is factual-within-simulation hidden state constrained by published possibility science.",
        },
        "test_plan": {
            "required_controls": anomaly.get("controls", []),
            "required_questions": architecture.get("required_questions", []),
            "eligible_observables": sorted(set(anomaly.get("observables", []) + architecture.get("observables", []))),
            "claim_ceiling": architecture.get("claim_ceiling"),
        },
        "source_ids": selected["source_ids"],
        "design_prior_receipt": {
            "origin_priors": ORIGIN_PRIORS,
            "warning": "These are entertainment simulation priors, not empirical frequencies for extraterrestrial life or anomalies.",
        },
    }
    commitment_payload = copy.deepcopy(private_payload)
    commitment = domain_hash(commitment_payload, "AXM-BLIND-FORGE-COMMITMENT-V1")
    public_bundle = {
        "schema": "axm.blind-player-mission.v1",
        "forge_version": "0.8.0",
        "system_id": system.get("system_id"),
        "system_name": system.get("name"),
        "target": {
            key: value
            for key, value in matrix["environment"].items()
            if key not in {"truth_note"}
        },
        "mission": (
            "Explore an unresolved physical or chemical possibility using broad measurements, independent controls, "
            "and claim ceilings. The player is not told whether the hidden starting state is instrumental, abiotic, "
            "prebiotic, biological, novel physics, or ultimately unresolved."
        ),
        "blindness_contract": {
            "forge_ai_completed_before_play": True,
            "player_ai_receives_private_scenario": False,
            "public_bundle_contains_commitment_only": True,
            "host_may_not_rewrite_private_state_after_commitment": True,
            "future_events_not_fully_predetermined": True,
            "post_play_reveal_can_be_verified": True,
        },
        "private_scenario_commitment_sha256": commitment,
        "evidence_ladder": registry["evidence_ladder"],
        "available_actions": ACTION_CATALOG,
        "initial_state": initial_player_state(commitment),
        "truth_boundary": [
            "An unusual observation is not automatically an anomaly.",
            "An anomaly is not automatically life or new physics.",
            "Life-like organization is not automatically a living system.",
            "A null result constrains only the tested channel and sensitivity.",
            "The player may finish without learning the private origin class.",
        ],
        "source_ids": selected["source_ids"],
    }
    leaks = scan_public_bundle_for_private_leaks(public_bundle, private_payload)
    if leaks:
        raise BlindForgeError(f"public bundle leaked private information: {leaks}")
    return private_payload, public_bundle


def initial_player_state(commitment: str) -> dict[str, Any]:
    return {
        "schema": "axm.blind-player-state.v1",
        "commitment_sha256": commitment,
        "turn": 0,
        "evidence_stage": 0,
        "claim_ceiling": "No unusual life-related claim is supported.",
        "tested_channels": [],
        "independent_confirmations": 0,
        "false_positive_controls_completed": 0,
        "mission_time_hours": 0.0,
        "knowledge_points": 0.0,
        "status": "active",
        "last_observation": None,
        "last_event_hash": "GENESIS",
    }


def scan_public_bundle_for_private_leaks(public_bundle: dict[str, Any], private_payload: dict[str, Any]) -> list[str]:
    serialized = canonical_json(public_bundle).lower()
    secret = private_payload["private_simulation_truth"]
    forbidden_values = {
        str(secret["resolution_secret"]),
        str(private_payload["selected_anomaly_family"]["id"]),
        str(private_payload["selected_life_architecture"]["id"]),
        str(private_payload["reasoned_candidate_matrix"]["selected_candidate_id"]),
    }
    leaks = [value for value in forbidden_values if value and value.lower() in serialized]
    forbidden_keys = {"private_simulation_truth", "resolution_secret", "selected_anomaly_family", "selected_life_architecture"}

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in forbidden_keys:
                    leaks.append(key)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(public_bundle)
    return sorted(set(leaks))


def _action(action_id: str) -> dict[str, Any]:
    for action in ACTION_CATALOG:
        if action["id"] == action_id:
            return action
    raise BlindForgeError(f"unknown blind action: {action_id}")


def _signal_for_action(private_payload: dict[str, Any], action: dict[str, Any]) -> float:
    traits = private_payload["private_simulation_truth"]["traits"]
    channel = action["channel"]
    channel_trait = {
        "general_pattern": "persistence",
        "repeatability": "persistence",
        "independent_replication": "persistence",
        "chemical_complexity": "chemical_complexity",
        "energy_transfer": "energy_organization",
        "elemental_compartmentalization": "compartmentalization",
        "adaptive_response": "adaptive_memory",
        "false_positive_control": "persistence",
        "mission_continuation": "persistence",
    }[channel]
    return float(traits[channel_trait]) * float(action["sensitivity"])


def _claim_ceiling(ladder: list[dict[str, Any]], stage: int) -> str:
    item = next((row for row in ladder if int(row["stage"]) == stage), ladder[0])
    return item["claim_ceiling"]


def resolve_blind_action(
    private_payload: dict[str, Any],
    public_bundle: dict[str, Any],
    state: dict[str, Any],
    action_id: str,
    entropy_token: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if state.get("status") != "active":
        raise BlindForgeError("blind session is not active")
    expected_commitment = domain_hash(private_payload, "AXM-BLIND-FORGE-COMMITMENT-V1")
    if public_bundle.get("private_scenario_commitment_sha256") != expected_commitment:
        raise BlindForgeError("private scenario does not match public commitment")
    if state.get("commitment_sha256") != expected_commitment:
        raise BlindForgeError("player state commitment mismatch")
    action = _action(action_id)
    turn = int(state["turn"]) + 1
    secret = private_payload["private_simulation_truth"]["resolution_secret"]
    rng = _rng(secret, str(turn), action_id, entropy_token, state.get("last_event_hash", "GENESIS"))
    expected_signal = _signal_for_action(private_payload, action)
    noise = rng.gauss(0.0, 0.12)
    realized_signal = max(0.0, min(1.0, expected_signal + noise))
    origin = private_payload["private_simulation_truth"]["origin_class"]
    false_positive_strength = {
        "instrumental_or_processing": 0.88,
        "known_abiotic_physics": 0.74,
        "unmodeled_abiotic_complexity": 0.58,
        "prebiotic_organized_chemistry": 0.42,
        "life_like_but_unresolved": 0.30,
        "candidate_living_system": 0.18,
        "novel_physics_unresolved": 0.46,
    }[origin]
    control_power = 0.0
    if action["channel"] == "false_positive_control":
        control_power = float(action["sensitivity"]) * (0.72 + rng.random() * 0.28)
    threshold = 0.46 + (0.10 if action["channel"] == "general_pattern" else 0.0)
    if action["channel"] == "mission_continuation":
        outcome_class = "preserved_without_resolution"
    elif control_power > false_positive_strength + 0.08:
        outcome_class = "known_controls_fail_to_reproduce"
    elif control_power >= false_positive_strength - 0.08:
        outcome_class = "control_result_ambiguous"
    elif action["channel"] == "false_positive_control":
        outcome_class = "candidate_partly_reproduced_by_control"
    elif realized_signal >= threshold + 0.16:
        outcome_class = "clear_repeatable_pattern"
    elif realized_signal >= threshold:
        outcome_class = "weak_or_contextual_pattern"
    else:
        outcome_class = "below_current_detection_threshold"

    updated = copy.deepcopy(state)
    updated["turn"] = turn
    updated["mission_time_hours"] = round(float(updated["mission_time_hours"]) + float(action["cost_hours"]), 6)
    tested = list(updated.get("tested_channels", []))
    if action["channel"] not in tested and action["channel"] != "mission_continuation":
        tested.append(action["channel"])
    updated["tested_channels"] = tested
    if action["independence"] >= 0.9 and outcome_class in {"clear_repeatable_pattern", "weak_or_contextual_pattern", "known_controls_fail_to_reproduce"}:
        updated["independent_confirmations"] = int(updated.get("independent_confirmations", 0)) + 1
    if action["channel"] == "false_positive_control":
        updated["false_positive_controls_completed"] = int(updated.get("false_positive_controls_completed", 0)) + 1

    current_stage = int(updated["evidence_stage"])
    candidate_stage = current_stage
    if outcome_class == "candidate_partly_reproduced_by_control":
        candidate_stage = max(0, current_stage - 1)
    elif outcome_class == "clear_repeatable_pattern":
        candidate_stage = min(current_stage + 1, 7)
    elif outcome_class in {"weak_or_contextual_pattern", "known_controls_fail_to_reproduce"} and current_stage == 0:
        candidate_stage = 1
    # Convergent requirements prevent a single high roll from climbing the entire ladder.
    if candidate_stage >= 2 and len(tested) < 2:
        candidate_stage = 1
    if candidate_stage >= 3 and updated["independent_confirmations"] < 1:
        candidate_stage = 2
    if candidate_stage >= 4 and updated["false_positive_controls_completed"] < 1:
        candidate_stage = 3
    if candidate_stage >= 5 and len(tested) < 5:
        candidate_stage = 4
    candidate_stage = min(candidate_stage, int(private_payload["private_simulation_truth"]["stage_ceiling"]))
    updated["evidence_stage"] = candidate_stage
    updated["claim_ceiling"] = _claim_ceiling(public_bundle["evidence_ladder"], candidate_stage)
    knowledge_delta = max(0.5, 2.0 + realized_signal * 7.0 + action["independence"] * 2.0)
    updated["knowledge_points"] = round(float(updated["knowledge_points"]) + knowledge_delta, 6)

    public_observation = {
        "channel": action["channel"],
        "outcome_class": outcome_class,
        "expected_sensitivity": action["sensitivity"],
        "realized_pattern_strength": round(realized_signal, 6),
        "detection_threshold": round(threshold, 6),
        "interpretation": {
            "below_current_detection_threshold": "Nothing exceeded this measurement's threshold. Other channels remain open.",
            "weak_or_contextual_pattern": "A context-dependent pattern is present, but instrumental and natural alternatives remain viable.",
            "clear_repeatable_pattern": "The tested channel contains a repeatable pattern. The claim ceiling advances by at most one stage.",
            "candidate_partly_reproduced_by_control": "A known control reproduces part of the candidate. Confidence decreases without erasing the historical observation.",
            "control_result_ambiguous": "The control neither fully explains nor cleanly excludes the candidate.",
            "known_controls_fail_to_reproduce": "The tested controls did not reproduce the pattern; untested alternatives remain.",
            "preserved_without_resolution": "The candidate is archived without forcing a conclusion.",
        }[outcome_class],
    }
    event_core = {
        "schema": "axm.blind-player-event.v1",
        "turn": turn,
        "action_id": action_id,
        "action_name": action["name"],
        "entropy_token_sha256": hashlib.sha256(entropy_token.encode("utf-8")).hexdigest(),
        "state_before_hash": domain_hash(state, "AXM-BLIND-PUBLIC-STATE-V1"),
        "observation": public_observation,
        "evidence_stage_after": candidate_stage,
        "claim_ceiling_after": updated["claim_ceiling"],
        "sealed_resolution_receipt": domain_hash(
            {
                "resolution_secret": secret,
                "turn": turn,
                "action_id": action_id,
                "entropy_token": entropy_token,
                "origin_class": origin,
                "observation": public_observation,
            },
            "AXM-BLIND-SEALED-RESOLUTION-V1",
        ),
        "private_origin_disclosed": False,
    }
    event_hash = domain_hash({**event_core, "previous_event_hash": state.get("last_event_hash", "GENESIS")}, "AXM-BLIND-PUBLIC-EVENT-V1")
    event = {**event_core, "previous_event_hash": state.get("last_event_hash", "GENESIS"), "event_hash": event_hash}
    updated["last_observation"] = public_observation
    updated["last_event_hash"] = event_hash
    if action_id == "move_on_preserve_candidate":
        updated["status"] = "archived_unresolved"
    return event, updated


def verify_private_reveal(private_payload: dict[str, Any], public_bundle: dict[str, Any]) -> dict[str, Any]:
    computed = domain_hash(private_payload, "AXM-BLIND-FORGE-COMMITMENT-V1")
    expected = public_bundle.get("private_scenario_commitment_sha256")
    leaks = scan_public_bundle_for_private_leaks(public_bundle, private_payload)
    return {
        "schema": "axm.blind-reveal-verification.v1",
        "valid": computed == expected and not leaks,
        "expected_commitment": expected,
        "computed_commitment": computed,
        "public_leaks": leaks,
    }


def verify_session(
    private_payload: dict[str, Any],
    public_bundle: dict[str, Any],
    events: list[dict[str, Any]],
    entropy_tokens: list[str],
) -> dict[str, Any]:
    if len(events) != len(entropy_tokens):
        return {"valid": False, "error": "event/token count mismatch"}
    reveal = verify_private_reveal(private_payload, public_bundle)
    if not reveal["valid"]:
        return {"valid": False, "error": "private reveal mismatch", "reveal": reveal}
    state = copy.deepcopy(public_bundle["initial_state"])
    checks: list[dict[str, Any]] = []
    for recorded, token in zip(events, entropy_tokens):
        rebuilt_event, rebuilt_state = resolve_blind_action(private_payload, public_bundle, state, recorded["action_id"], token)
        valid = canonical_json(rebuilt_event) == canonical_json(recorded)
        checks.append({"turn": recorded.get("turn"), "valid": valid, "event_hash": recorded.get("event_hash")})
        if not valid:
            return {"valid": False, "checks": checks, "error": "event mismatch"}
        state = rebuilt_state
    return {"valid": True, "checks": checks, "final_state": state, "reveal": reveal}


def write_blind_forge_session(output: Path, system: dict[str, Any], private_payload: dict[str, Any], public_bundle: dict[str, Any]) -> dict[str, Any]:
    from .blind_console import render_blind_console

    private_dir = output / "forge_private"
    public_dir = output / "player_public"
    private_dir.mkdir(parents=True, exist_ok=True)
    public_dir.mkdir(parents=True, exist_ok=True)
    (private_dir / "hidden_scenario.json").write_text(json.dumps(private_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (private_dir / "ENTROPY_TOKENS.json").write_text("[]\n", encoding="utf-8")
    public_system = copy.deepcopy(system)
    public_system["blind_forge"] = {
        "private_scenario_commitment_sha256": public_bundle["private_scenario_commitment_sha256"],
        "private_scenario_included": False,
        "player_visibility": "public facts and observations only",
    }
    (public_dir / "system_public.json").write_text(json.dumps(public_system, indent=2, ensure_ascii=False), encoding="utf-8")
    (public_dir / "mission_bundle.json").write_text(json.dumps(public_bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    (public_dir / "player_state.json").write_text(json.dumps(public_bundle["initial_state"], indent=2, ensure_ascii=False), encoding="utf-8")
    (public_dir / "event_ledger.jsonl").write_text("", encoding="utf-8")
    (public_dir / "player_console.html").write_text(render_blind_console(public_bundle, public_bundle["initial_state"], []), encoding="utf-8")
    player_handoff = (
        "AXM BLIND EXPEDITION — PLAYER HANDOFF\n\n"
        "You are the explorer. You do not know the sealed starting phenomenon.\n"
        "Read mission_bundle.json, system_public.json, player_state.json, and player_console.html.\n"
        "Choose exactly one action_id from mission_bundle.json and return it to the host.\n"
        "The host resolves the action and returns refreshed public files.\n"
        "Do not request forge_private files until the agreed reveal point.\n"
        "An observation may remain null, ambiguous, explained by controls, or unresolved.\n"
    )
    (public_dir / "PLAYER_HANDOFF.txt").write_text(player_handoff, encoding="utf-8")
    handoff = (
        "AXM BLIND PLAYER HANDOFF\n\n"
        "Give only the player_public directory to the exploring human or AI.\n"
        "Keep forge_private inaccessible to the player until the chosen reveal point.\n"
        "The public commitment proves the hidden scenario existed before play.\n"
        "A host resolves submitted actions and refreshes player_state.json and player_console.html.\n"
    )
    (output / "BLIND_FORGE_HANDOFF.txt").write_text(handoff, encoding="utf-8")
    return {
        "private_scenario": str(private_dir / "hidden_scenario.json"),
        "public_bundle": str(public_dir / "mission_bundle.json"),
        "player_console": str(public_dir / "player_console.html"),
        "commitment": public_bundle["private_scenario_commitment_sha256"],
    }


def resolve_session_action(output: Path, action_id: str, entropy_token: str) -> dict[str, Any]:
    from .blind_console import render_blind_console

    private_path = output / "forge_private" / "hidden_scenario.json"
    public_dir = output / "player_public"
    private_payload = json.loads(private_path.read_text(encoding="utf-8"))
    public_bundle = json.loads((public_dir / "mission_bundle.json").read_text(encoding="utf-8"))
    state = json.loads((public_dir / "player_state.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in (public_dir / "event_ledger.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    event, updated = resolve_blind_action(private_payload, public_bundle, state, action_id, entropy_token)
    events.append(event)
    (public_dir / "event_ledger.jsonl").write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in events) + "\n", encoding="utf-8")
    (public_dir / "player_state.json").write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8")
    (public_dir / "player_console.html").write_text(render_blind_console(public_bundle, updated, events), encoding="utf-8")
    token_path = output / "forge_private" / "ENTROPY_TOKENS.json"
    tokens = json.loads(token_path.read_text(encoding="utf-8"))
    tokens.append(entropy_token)
    token_path.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
    return {"event": event, "state": updated}


def reveal_session(output: Path) -> dict[str, Any]:
    private_payload = json.loads((output / "forge_private" / "hidden_scenario.json").read_text(encoding="utf-8"))
    public_bundle = json.loads((output / "player_public" / "mission_bundle.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in (output / "player_public" / "event_ledger.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    tokens = json.loads((output / "forge_private" / "ENTROPY_TOKENS.json").read_text(encoding="utf-8"))
    verification = verify_session(private_payload, public_bundle, events, tokens)
    reveal_dir = output / "post_play_reveal"
    reveal_dir.mkdir(parents=True, exist_ok=True)
    (reveal_dir / "hidden_scenario_revealed.json").write_text(json.dumps(private_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (reveal_dir / "verification.json").write_text(json.dumps(verification, indent=2, ensure_ascii=False), encoding="utf-8")
    return verification
