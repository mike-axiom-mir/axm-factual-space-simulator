from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from axm_star_sim.contact_horizon import (
    build_contact_actions,
    contact_horizon_snapshot,
    validate_contact_horizon_registry,
)
from axm_star_sim.generator import generate_system
from axm_star_sim.runtime import initial_runtime_state, resolve_turn, verify_recorded_event
from axm_star_sim.technology_core import eligible_core_ids, select_technology_core, validate_technology_registry
from axm_star_sim.thread_engine import build_action_menu
from axm_star_sim.validation import validate_system


def deterministic_sequence(seed: str, turns: int) -> list[str]:
    system = generate_system(seed).to_dict()
    state = initial_runtime_state(system)
    hashes: list[str] = []
    for turn in range(turns):
        actions = state["action_menu"]["actions"]
        action = actions[turn % len(actions)]["action_id"]
        event, state = resolve_turn(system=system, state=state, action=action, entropy_mode="deterministic")
        hashes.append(event["event_hash"])
    return hashes


def prime_contact_state(system: dict, suffix: int) -> dict:
    state = initial_runtime_state(system)
    state["turn"] = 100000 + suffix
    work = state["contact_horizon"]["scientific_work"]
    work["total_science_actions"] = 1000 + suffix
    work["independent_observation_context_ids"] = [f"context-{i}" for i in range(12)]
    work["cross_validations"] = 80
    work["false_positive_eliminations"] = 50
    work["passive_search_hours"] = 10000.0
    state["action_menu"] = build_action_menu(system, state)
    return state


def main() -> int:
    validate_technology_registry()
    validate_contact_horizon_registry()
    eligible = eligible_core_ids()
    systems = 250
    turns_per_system = 12
    selection_population = 1000
    outcomes: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    runtime_cores: Counter[str] = Counter()
    population_cores: Counter[str] = Counter()
    contact_initial_states = 0
    contact_actions_before_unlock = 0
    min_menu = 99
    max_menu = 0
    verified_events = 0

    for index in range(selection_population):
        selected, _core, receipt = select_technology_core(f"AXM-V06-SELECTION-{index:05d}")
        if receipt["manual_technology_choice"] or receipt["weights"] != "none; every eligible catalog core occupies one sorted slot":
            raise AssertionError("selection receipt broke equal-catalog policy")
        population_cores[selected] += 1
    if set(population_cores) != set(eligible):
        raise AssertionError({"missing_cores": sorted(set(eligible) - set(population_cores))})

    for system_index in range(systems):
        seed = f"AXM-V06-STRESS-{system_index:04d}"
        system = generate_system(seed).to_dict()
        validate_system(system)
        profile = system["ship"]["technology_core"]
        core_id = profile["selected_core_id"]
        runtime_cores[core_id] += 1
        state = initial_runtime_state(system)
        initial_contact = state["contact_horizon"]
        if initial_contact["candidate_id"] is not None or initial_contact["candidate_classes"]:
            raise AssertionError({"seed": seed, "error": "master seed preselected contact state"})
        if build_contact_actions(system, state):
            contact_actions_before_unlock += 1
        contact_initial_states += 1

        for turn in range(turns_per_system):
            actions = state["action_menu"]["actions"]
            min_menu = min(min_menu, len(actions))
            max_menu = max(max_menu, len(actions))
            action = actions[(system_index + turn * 3) % len(actions)]
            event, updated = resolve_turn(system=system, state=state, action=action["action_id"], entropy_mode="deterministic")
            check, rebuilt = verify_recorded_event(system, state, event)
            if not check["valid"] or rebuilt != updated:
                raise AssertionError({"seed": seed, "turn": turn + 1, "check": check})
            if event["contact_horizon_after"]["evidence_stage"] != 0:
                raise AssertionError({"seed": seed, "turn": turn + 1, "error": "contact stage advanced before long horizon"})
            envelope = event["physics_expectation"]["technology_envelope"]
            if envelope["selected_core_id"] != core_id:
                raise AssertionError({"seed": seed, "turn": turn + 1, "error": "physics/core mismatch"})
            if envelope["propulsion"]["quantitative_performance_status"] != "blocked_unknown":
                raise AssertionError({"seed": seed, "turn": turn + 1, "error": "unpublished propulsion promoted"})
            verified_events += 1
            outcomes[event["outcome"]["id"]] += 1
            categories[event["action_record"]["category"]] += 1
            state = updated

    if contact_actions_before_unlock:
        raise AssertionError({"contact_actions_before_unlock": contact_actions_before_unlock})

    contact_trials = 80
    contact_trial_stages: Counter[int] = Counter()
    contact_events_verified = 0
    for index in range(contact_trials):
        system = generate_system(f"AXM-V06-CONTACT-{index:03d}").to_dict()
        state = prime_contact_state(system, index)
        snapshot = contact_horizon_snapshot(state)
        if not snapshot["readiness"]["ready"]:
            raise AssertionError({"trial": index, "error": "primed horizon not ready"})
        actions = [a for a in state["action_menu"]["actions"] if a["action_id"].startswith("contact-horizon:")]
        if not actions:
            raise AssertionError({"trial": index, "error": "no contact research action after gates"})
        event, updated = resolve_turn(system=system, state=state, action=actions[index % len(actions)]["action_id"], entropy_mode="deterministic")
        check, rebuilt = verify_recorded_event(system, state, event)
        if not check["valid"] or rebuilt != updated:
            raise AssertionError({"trial": index, "check": check})
        stage = int(event["contact_horizon_after"]["evidence_stage"])
        if stage > 2:
            raise AssertionError({"trial": index, "error": "single deep-search event jumped evidence ladder", "stage": stage})
        if event["contact_horizon_after"]["confirmed_external_agency"]:
            raise AssertionError({"trial": index, "error": "single event confirmed agency"})
        contact_trial_stages[stage] += 1
        contact_events_verified += 1

    reproducibility_pairs = 30
    for index in range(reproducibility_pairs):
        seed = f"AXM-V06-REPRO-{index:03d}"
        if deterministic_sequence(seed, 10) != deterministic_sequence(seed, 10):
            raise AssertionError({"seed": seed, "error": "deterministic sequence diverged"})

    result = {
        "schema": "axm.v0.6-stress-report.v1",
        "status": "PASS",
        "technology_registry_valid": True,
        "contact_horizon_registry_valid": True,
        "eligible_technology_cores": eligible,
        "selection_population": selection_population,
        "selection_distribution": dict(sorted(population_cores.items())),
        "systems": systems,
        "turns_per_system": turns_per_system,
        "events_replay_verified": verified_events,
        "runtime_core_distribution": dict(sorted(runtime_cores.items())),
        "initial_contact_states_checked": contact_initial_states,
        "master_seed_preselected_contact_states": 0,
        "contact_actions_before_step_100000": 0,
        "contact_horizon_trials": contact_trials,
        "contact_events_replay_verified": contact_events_verified,
        "contact_stage_after_one_search_distribution": {str(k): v for k, v in sorted(contact_trial_stages.items())},
        "single_search_confirmed_external_agency": 0,
        "deterministic_reproducibility_pairs": reproducibility_pairs,
        "deterministic_turns_per_pair": 10,
        "action_categories_observed": dict(sorted(categories.items())),
        "outcomes_observed": dict(sorted(outcomes.items())),
        "dynamic_menu_size": {"minimum": min_menu, "maximum": max_menu},
        "unpublished_propulsion_performance_promoted": False,
    }
    root = Path(__file__).resolve().parents[1]
    path = root / "docs" / "stress_report_v0_6_0.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
