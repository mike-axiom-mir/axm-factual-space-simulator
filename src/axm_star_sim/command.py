from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .runtime import available_actions, initial_runtime_state, normalize_action
from .thread_engine import action_by_input, build_action_menu
from .rooted_crew import ELIGIBLE, evaluate_menu_record, load_default_crew, load_root_kernel

COMMAND_SCHEMA = "axm.command-decision.v1"
SESSION_SCHEMA = "axm.command-council-session.v1"
DISCUSSION_SCHEMA = "axm.command-council-message.v1"

COMMAND_MODES: dict[str, dict[str, Any]] = {
    "autonomous_deterministic": {
        "number": 1,
        "title": "Deterministic Crew Expedition",
        "authority": "deterministic_crew",
        "description": (
            "The deterministic crew continuously chooses its own next action, balancing curiosity, "
            "mission value, ship limits, and danger. The same system state produces the same decision."
        ),
        "requires": [],
    },
    "ai_command": {
        "number": 2,
        "title": "AI Command",
        "authority": "ai_commander",
        "description": (
            "An AI commander chooses the action. The deterministic crew supplies assessments and then "
            "executes the valid command without silently changing it."
        ),
        "requires": ["ai_proposal"],
    },
    "human_command": {
        "number": 3,
        "title": "Human Command",
        "authority": "human_commander",
        "description": (
            "A human commander chooses the action. The deterministic crew supplies assessments and then "
            "executes the valid command without silently changing it."
        ),
        "requires": ["human_proposal"],
    },
    "collaborative_command": {
        "number": 4,
        "title": "Human + AI Collaborative Command",
        "authority": "human_ai_council",
        "description": (
            "The human and AI each cast one explicit command vote. Matching votes execute. Different "
            "votes open a discussion session; no hidden tie-breaker selects a direction."
        ),
        "requires": ["human_proposal", "ai_proposal"],
    },
}

CREW_PROFILES: list[dict[str, Any]] = [
    {
        "id": "science",
        "name": "Science Seat",
        "weights": {"curiosity": 0.50, "safety": 0.16, "efficiency": 0.10, "mission": 0.24},
    },
    {
        "id": "navigation",
        "name": "Navigation Seat",
        "weights": {"curiosity": 0.16, "safety": 0.32, "efficiency": 0.34, "mission": 0.18},
    },
    {
        "id": "engineering",
        "name": "Engineering Seat",
        "weights": {"curiosity": 0.12, "safety": 0.43, "efficiency": 0.33, "mission": 0.12},
    },
    {
        "id": "watch",
        "name": "Hazard Watch",
        "weights": {"curiosity": 0.08, "safety": 0.64, "efficiency": 0.12, "mission": 0.16},
    },
    {
        "id": "mission",
        "name": "Mission Seat",
        "weights": {"curiosity": 0.24, "safety": 0.20, "efficiency": 0.16, "mission": 0.40},
    },
]

ACTION_TRAITS: dict[str, dict[str, float]] = {
    "probe": {"curiosity": 0.90, "risk": 0.70, "cost": 0.62, "mission": 0.82},
    "patient_observation": {"curiosity": 0.75, "risk": 0.16, "cost": 0.28, "mission": 0.72},
    "instrument": {"curiosity": 0.82, "risk": 0.34, "cost": 0.68, "mission": 0.78},
    "engineering": {"curiosity": 0.28, "risk": 0.12, "cost": 0.38, "mission": 0.72},
    "move_on": {"curiosity": 0.08, "risk": 0.06, "cost": 0.10, "mission": 0.20},
    "general": {"curiosity": 0.50, "risk": 0.35, "cost": 0.40, "mission": 0.50},
}


def canonical_hash(value: Any, domain: str = "AXM-COMMAND-HASH-V1") -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(f"{domain}|{raw}".encode("utf-8")).hexdigest()


def mode_catalog() -> dict[str, dict[str, Any]]:
    return copy.deepcopy(COMMAND_MODES)


def validate_mode(mode: str) -> str:
    if mode not in COMMAND_MODES:
        raise ValueError(f"unknown command mode: {mode}")
    return mode


def action_category(action: str) -> str:
    text = action.casefold()
    if any(word in text for word in ("probe", "close pass", "deploy")):
        return "probe"
    if any(word in text for word in ("delay", "longer", "complete phase", "observe")):
        return "patient_observation"
    if any(word in text for word in ("spectroscopy", "sensor", "map", "orbit fitting", "viewing geometry", "reconfigure")):
        return "instrument"
    if any(word in text for word in ("ignore", "continue", "direct route", "conserve")):
        return "move_on"
    return "general"


def _condition_factors(state: dict[str, Any]) -> dict[str, float]:
    r = state["resources"]
    hull = float(r["hull_integrity_percent"]) / 100.0
    sensors = float(r["sensor_health_percent"]) / 100.0
    fuel = float(r["fuel_percent"]) / 100.0
    reactor = float(r["reactor_reserve_percent"]) / 100.0
    heat = float(r["heat_percent"]) / 100.0
    safety_margin = max(0.0, min(1.0, (hull + sensors + fuel + reactor + (1.0 - heat)) / 5.0))
    scarcity = max(0.0, min(1.0, 1.0 - ((fuel + reactor + sensors) / 3.0)))
    danger_pressure = max(0.0, min(1.0, (1.0 - hull) * 0.35 + heat * 0.35 + (1.0 - sensors) * 0.30))
    return {"safety_margin": safety_margin, "scarcity": scarcity, "danger_pressure": danger_pressure}


def _action_vector(
    action: str,
    state: dict[str, Any],
    opportunity: dict[str, Any],
    *,
    category_override: str | None = None,
    menu_priority: float = 0.9,
) -> dict[str, float]:
    category = category_override or action_category(action)
    traits = copy.deepcopy(ACTION_TRAITS[category])
    factors = _condition_factors(state)
    tone = opportunity.get("tone", "mystery")

    curiosity = traits["curiosity"]
    mission = min(1.0, traits["mission"] + max(-0.12, min(0.12, (menu_priority - 0.9) * 0.35)))
    repeat_count = sum(1 for item in state.get("timeline", []) if item.get("action") == action)
    # Repeating the same measurement eventually yields less new information. This is deterministic,
    # state-dependent information saturation rather than hidden randomness.
    curiosity = max(0.0, curiosity - min(0.42, repeat_count * 0.14))
    mission = max(0.0, mission - min(0.30, repeat_count * 0.10))
    if tone in {"wonder", "mystery", "contact"}:
        curiosity = min(1.0, curiosity + 0.08)
    if tone in {"engineering", "danger"} and category in {"instrument", "patient_observation"}:
        mission = min(1.0, mission + 0.08)

    effective_risk = min(1.0, traits["risk"] * (1.20 - 0.45 * factors["safety_margin"]) + factors["danger_pressure"] * 0.25)
    effective_cost = min(1.0, traits["cost"] + factors["scarcity"] * traits["cost"] * 0.45)
    safety = 1.0 - effective_risk
    efficiency = 1.0 - effective_cost

    if category == "probe" and int(state["resources"]["probe_count"]) <= 0:
        curiosity = 0.0
        safety = 0.0
        efficiency = 0.0
        mission = 0.0

    return {
        "category": category,
        "curiosity": round(curiosity, 6),
        "safety": round(safety, 6),
        "efficiency": round(efficiency, 6),
        "mission": round(mission, 6),
        "effective_risk": round(effective_risk, 6),
        "effective_cost": round(effective_cost, 6),
        "repeat_count": repeat_count,
        "information_saturation": round(min(0.42, repeat_count * 0.14), 6),
    }


def _tie_value(system: dict[str, Any], state: dict[str, Any], action: str, seat_id: str) -> float:
    raw = f"AXM-CREW-TIE-V1|{system['master_seed']}|{state['turn']}|{seat_id}|{action}"
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:13], 16) / float(0x1FFFFFFFFFFFFF)


def crew_assessment(system: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    menu = state.get("action_menu") or build_action_menu(system, state)
    opportunity = system["adventure"]["selected_opportunity"]
    action_rows: list[dict[str, Any]] = []
    for record in menu["actions"]:
        action = str(record["label"])
        vector = _action_vector(
            action,
            state,
            opportunity,
            category_override=str(record.get("category") or action_category(action)),
            menu_priority=float(record.get("priority", 0.9)),
        )
        root_evaluation = evaluate_menu_record(record, state)
        row = {
            "action": action,
            "action_id": record["action_id"],
            "source_thread": record.get("source_thread"),
            "intent": record.get("intent"),
            "vector": vector,
            "root_evaluation": root_evaluation,
            "root_eligible": root_evaluation["overall_verdict"] == ELIGIBLE,
            "seat_scores": {},
        }
        for seat in CREW_PROFILES:
            weights = seat["weights"]
            if not row["root_eligible"]:
                score = -1.0
            else:
                score = (
                    vector["curiosity"] * weights["curiosity"]
                    + vector["safety"] * weights["safety"]
                    + vector["efficiency"] * weights["efficiency"]
                    + vector["mission"] * weights["mission"]
                )
                # Wisdom is considered before efficiency. The utility weights only rank root-eligible options.
                score += 0.12 * root_evaluation["root_evaluations"][3]["wisdom_score"]
                score -= min(0.36, vector["repeat_count"] * 0.06)
            row["seat_scores"][seat["id"]] = round(score, 8)
        action_rows.append(row)

    if not action_rows:
        raise ValueError("the dynamic action menu contains no executable actions")

    votes = []
    for seat in CREW_PROFILES:
        eligible_rows = [row for row in action_rows if row["root_eligible"]]
        if not eligible_rows:
            raise ValueError("the root perspective produced no eligible crew action; command clarification is required")
        ranked = sorted(
            eligible_rows,
            key=lambda row: (row["seat_scores"][seat["id"]], _tie_value(system, state, row["action_id"], seat["id"])),
            reverse=True,
        )
        winner = ranked[0]
        votes.append({
            "seat_id": seat["id"],
            "seat_name": seat["name"],
            "action": winner["action"],
            "action_id": winner["action_id"],
            "score": winner["seat_scores"][seat["id"]],
            "reason": (
                f"Selected from deterministic weights: curiosity {seat['weights']['curiosity']:.2f}, "
                f"safety {seat['weights']['safety']:.2f}, efficiency {seat['weights']['efficiency']:.2f}, "
                f"mission {seat['weights']['mission']:.2f}."
            ),
        })

    for row in action_rows:
        row["crew_average"] = round(sum(row["seat_scores"].values()) / len(CREW_PROFILES), 8)
        row["vote_count"] = sum(1 for vote in votes if vote["action_id"] == row["action_id"])

    ranked_actions = sorted(
        action_rows,
        key=lambda row: (
            row["root_eligible"],
            row["vote_count"],
            row["crew_average"],
            _tie_value(system, state, row["action_id"], "whole-crew"),
        ),
        reverse=True,
    )
    recommendation = ranked_actions[0]["action"]
    warnings = command_warnings(system, state, recommendation)
    return {
        "schema": "axm.deterministic-crew-assessment.v2",
        "turn": int(state["turn"]) + 1,
        "action_menu_version": menu.get("menu_version"),
        "action_menu_sha256": canonical_hash(menu, "AXM-ACTION-MENU-V1"),
        "crew_profiles": copy.deepcopy(CREW_PROFILES),
        "default_crew_start": load_default_crew(),
        "immutable_root_kernel": load_root_kernel(),
        "actions": ranked_actions,
        "votes": votes,
        "recommended_action": recommendation,
        "recommended_action_id": ranked_actions[0]["action_id"],
        "warnings": warnings,
        "determinism_contract": (
            "Given the same generator version, system, runtime state, dynamic action menu, immutable root kernel, and crew profiles, this assessment is reproducible. "
            "Efficiency ranks only actions that remain eligible after Truth, Continuity, Agency, and Wisdom evaluation."
        ),
    }


def command_warnings(system: dict[str, Any], state: dict[str, Any], action: str) -> list[str]:
    record = action_by_input(system, state, action)
    normalized = str(record["label"])
    category = str(record.get("category") or action_category(normalized))
    r = state["resources"]
    warnings: list[str] = []
    if category == "probe" and int(r["probe_count"]) <= 0:
        warnings.append("IMPOSSIBLE: no probes remain.")
    if category in {"probe", "instrument"} and float(r["sensor_health_percent"]) < 45:
        warnings.append("Sensor health is below 45%; evidence quality may be poor.")
    if category in {"probe", "instrument"} and float(r["reactor_reserve_percent"]) < 25:
        warnings.append("Reactor reserve is below 25%; the action may reduce later options.")
    if category == "probe" and float(r["heat_percent"]) > 70:
        warnings.append("Ship heat is already above 70%; close operations carry elevated thermal risk.")
    if category == "move_on":
        warnings.append("Moving on protects resources but may permanently close the present observation window.")
    return warnings


def proposal(actor: str, action: str, rationale: str = "") -> dict[str, Any]:
    if actor not in {"human", "ai"}:
        raise ValueError("proposal actor must be 'human' or 'ai'")
    return {
        "actor": actor,
        "action": action,
        "rationale": rationale.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _normalize_proposal(
    system: dict[str, Any], state: dict[str, Any], value: dict[str, Any] | None, actor: str
) -> dict[str, Any]:
    if value is None:
        raise ValueError(f"{actor} proposal is required")
    action = normalize_action(system, str(value.get("action", "")), state)
    record = action_by_input(system, state, action)
    root_evaluation = evaluate_menu_record(record, state)
    if root_evaluation["overall_verdict"] != ELIGIBLE:
        raise ValueError(
            f"{actor} proposal is not executable under the immutable root perspective: "
            f"{root_evaluation['overall_verdict']}"
        )
    return {
        "actor": actor,
        "action": action,
        "rationale": str(value.get("rationale", "")).strip(),
        "created_at": value.get("created_at") or datetime.now(timezone.utc).isoformat(),
        "root_evaluation": root_evaluation,
    }


def _resolved_decision(
    *,
    mode: str,
    action: str,
    assessment: dict[str, Any],
    proposals: list[dict[str, Any]],
    authority: str,
    resolution_method: str,
    warnings: list[str],
    discussion_session_id: str | None = None,
    resolution_summary: str = "",
) -> dict[str, Any]:
    matching = next((row for row in assessment.get("actions", []) if row.get("action") == action), None)
    decision = {
        "schema": COMMAND_SCHEMA,
        "mode": mode,
        "mode_number": COMMAND_MODES[mode]["number"],
        "status": "resolved",
        "authority": authority,
        "selected_action": action,
        "selected_action_id": matching.get("action_id") if matching else None,
        "resolution_method": resolution_method,
        "proposals": proposals,
        "crew_assessment": assessment,
        "crew_recommendation_followed": action == assessment["recommended_action"],
        "warnings": warnings,
        "discussion_session_id": discussion_session_id,
        "resolution_summary": resolution_summary.strip(),
    }
    decision["command_hash"] = canonical_hash(decision)
    return decision


def plan_command(
    *,
    system: dict[str, Any],
    state: dict[str, Any],
    mode: str,
    human_proposal: dict[str, Any] | None = None,
    ai_proposal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_mode(mode)
    assessment = crew_assessment(system, state)

    if mode == "autonomous_deterministic":
        action = assessment["recommended_action"]
        return {
            "status": "resolved",
            "decision": _resolved_decision(
                mode=mode,
                action=action,
                assessment=assessment,
                proposals=[],
                authority="deterministic_crew",
                resolution_method="deterministic_crew_vote",
                warnings=command_warnings(system, state, action),
                resolution_summary="The crew selected the highest reproducible vote-and-utility result.",
            ),
        }

    if mode == "ai_command":
        ai = _normalize_proposal(system, state, ai_proposal, "ai")
        return {
            "status": "resolved",
            "decision": _resolved_decision(
                mode=mode,
                action=ai["action"],
                assessment=assessment,
                proposals=[ai],
                authority="ai_commander",
                resolution_method="ai_command",
                warnings=command_warnings(system, state, ai["action"]),
                resolution_summary="The deterministic crew executed the AI command as supplied.",
            ),
        }

    if mode == "human_command":
        human = _normalize_proposal(system, state, human_proposal, "human")
        return {
            "status": "resolved",
            "decision": _resolved_decision(
                mode=mode,
                action=human["action"],
                assessment=assessment,
                proposals=[human],
                authority="human_commander",
                resolution_method="human_command",
                warnings=command_warnings(system, state, human["action"]),
                resolution_summary="The deterministic crew executed the human command as supplied.",
            ),
        }

    human = _normalize_proposal(system, state, human_proposal, "human")
    ai = _normalize_proposal(system, state, ai_proposal, "ai")
    if human["action"] == ai["action"]:
        action = human["action"]
        return {
            "status": "resolved",
            "decision": _resolved_decision(
                mode=mode,
                action=action,
                assessment=assessment,
                proposals=[human, ai],
                authority="human_ai_council",
                resolution_method="matching_votes",
                warnings=command_warnings(system, state, action),
                resolution_summary="Human and AI independently selected the same action.",
            ),
        }

    session_basis = {
        "system_id": system["system_id"],
        "turn": int(state["turn"]) + 1,
        "state_hash": canonical_hash(state, "AXM-COMMAND-STATE-V1"),
        "human": human,
        "ai": ai,
    }
    session_id = f"council-{canonical_hash(session_basis)[:16]}"
    session = {
        "schema": SESSION_SCHEMA,
        "session_id": session_id,
        "status": "discussion_required",
        "mode": mode,
        "system_id": system["system_id"],
        "turn": int(state["turn"]) + 1,
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "state_before_sha256": canonical_hash(state, "AXM-COMMAND-STATE-V1"),
        "proposals": {"human": human, "ai": ai},
        "crew_assessment": assessment,
        "rule": (
            "Human and AI have one command vote each. Different votes have no automatic tie-break. "
            "They must exchange reasons and submit matching final votes before execution."
        ),
        "discussion": [],
        "last_message_hash": None,
    }
    session["session_hash"] = canonical_hash(session, "AXM-COMMAND-SESSION-V1")
    return {"status": "discussion_required", "session": session}


def append_discussion_message(
    *,
    system: dict[str, Any],
    state: dict[str, Any] | None = None,
    session: dict[str, Any],
    speaker: str,
    message: str,
    proposed_action: str | None = None,
) -> dict[str, Any]:
    if session.get("status") != "discussion_required":
        raise ValueError("command council session is not open for discussion")
    if state is None:
        state = initial_runtime_state(system)
        frozen_rows = session.get("crew_assessment", {}).get("actions", [])
        if frozen_rows:
            state["turn"] = max(0, int(session.get("turn", 1)) - 1)
            state["action_menu"] = {
                "schema": "axm.dynamic-action-menu.v1",
                "menu_version": int(session.get("turn", 1)),
                "generated_from_turn": state["turn"],
                "actions": [
                    {"index": index, "label": row["action"], "action_id": row.get("action_id", row["action"])}
                    for index, row in enumerate(frozen_rows, start=1)
                ],
            }
    if speaker not in {"human", "ai"}:
        raise ValueError("speaker must be 'human' or 'ai'")
    clean_message = message.strip()
    if not clean_message:
        raise ValueError("discussion message cannot be empty")
    action = normalize_action(system, proposed_action, state) if proposed_action else None
    entry = {
        "schema": DISCUSSION_SCHEMA,
        "session_id": session["session_id"],
        "index": len(session.get("discussion", [])) + 1,
        "speaker": speaker,
        "message": clean_message,
        "proposed_action": action,
        "previous_message_hash": session.get("last_message_hash"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    entry["message_hash"] = canonical_hash(entry, "AXM-COMMAND-DISCUSSION-V1")
    updated = copy.deepcopy(session)
    updated.setdefault("discussion", []).append(entry)
    updated["last_message_hash"] = entry["message_hash"]
    if action:
        updated["proposals"][speaker] = proposal(speaker, action, clean_message)
    base = {k: v for k, v in updated.items() if k != "session_hash"}
    updated["session_hash"] = canonical_hash(base, "AXM-COMMAND-SESSION-V1")
    return updated


def resolve_collaboration(
    *,
    system: dict[str, Any],
    state: dict[str, Any],
    session: dict[str, Any],
    human_final_action: str,
    ai_final_action: str,
    summary: str = "",
) -> dict[str, Any]:
    if session.get("status") != "discussion_required":
        raise ValueError("command council session is not awaiting resolution")
    if session.get("system_id") != system.get("system_id"):
        raise ValueError("command council session belongs to a different system")
    if int(session.get("turn", -1)) != int(state["turn"]) + 1:
        raise ValueError("command council session no longer matches the current turn")
    expected_state_hash = canonical_hash(state, "AXM-COMMAND-STATE-V1")
    if session.get("state_before_sha256") != expected_state_hash:
        raise ValueError("command council session no longer matches the current runtime state")

    human_action = normalize_action(system, human_final_action, state)
    ai_action = normalize_action(system, ai_final_action, state)
    if human_action != ai_action:
        raise ValueError("final human and AI votes still differ; discussion must continue")

    assessment = crew_assessment(system, state)
    proposals = [
        proposal("human", human_action, "Final post-discussion vote."),
        proposal("ai", ai_action, "Final post-discussion vote."),
    ]
    decision = _resolved_decision(
        mode="collaborative_command",
        action=human_action,
        assessment=assessment,
        proposals=proposals,
        authority="human_ai_council",
        resolution_method="post_discussion_consensus",
        warnings=command_warnings(system, state, human_action),
        discussion_session_id=session["session_id"],
        resolution_summary=summary or "Human and AI reached matching final votes after discussion.",
    )
    decision["initial_proposals"] = copy.deepcopy(session.get("proposals", {}))
    decision["discussion_transcript"] = copy.deepcopy(session.get("discussion", []))
    decision["discussion_rule"] = session.get("rule")
    decision["discussion_transcript_hash"] = canonical_hash(session.get("discussion", []), "AXM-COMMAND-TRANSCRIPT-V1")
    decision["command_hash"] = canonical_hash({k: v for k, v in decision.items() if k != "command_hash"})
    return decision
