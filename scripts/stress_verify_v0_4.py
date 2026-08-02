from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from axm_star_sim.generator import generate_system
from axm_star_sim.runtime import initial_runtime_state, resolve_turn, verify_recorded_event


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


def main() -> int:
    systems = 300
    turns_per_system = 12
    outcomes: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    thread_kinds: Counter[str] = Counter()
    max_menu = 0
    min_menu = 99
    verified_events = 0

    for system_index in range(systems):
        seed = f"AXM-V04-STRESS-{system_index:04d}"
        system = generate_system(seed).to_dict()
        state = initial_runtime_state(system)
        for turn in range(turns_per_system):
            actions = state["action_menu"]["actions"]
            max_menu = max(max_menu, len(actions))
            min_menu = min(min_menu, len(actions))
            action = actions[(system_index + turn * 3) % len(actions)]
            event, updated = resolve_turn(
                system=system,
                state=state,
                action=action["action_id"],
                entropy_mode="deterministic",
            )
            check, rebuilt = verify_recorded_event(system, state, event)
            if not check["valid"]:
                raise AssertionError({"seed": seed, "turn": turn + 1, "check": check})
            if rebuilt != updated:
                raise AssertionError({"seed": seed, "turn": turn + 1, "error": "replayed state mismatch"})
            verified_events += 1
            outcomes[event["outcome"]["id"]] += 1
            categories[event["action_record"]["category"]] += 1
            thread_kinds.update(updated["threads"].keys())
            state = updated

    reproducibility_pairs = 40
    for index in range(reproducibility_pairs):
        seed = f"AXM-V04-REPRO-{index:03d}"
        first = deterministic_sequence(seed, 10)
        second = deterministic_sequence(seed, 10)
        if first != second:
            raise AssertionError({"seed": seed, "error": "deterministic causal sequence diverged"})

    result = {
        "schema": "axm.v0.4-stress-report.v1",
        "status": "PASS",
        "systems": systems,
        "turns_per_system": turns_per_system,
        "events_replay_verified": verified_events,
        "deterministic_reproducibility_pairs": reproducibility_pairs,
        "deterministic_turns_per_pair": 10,
        "action_categories_observed": dict(sorted(categories.items())),
        "outcomes_observed": dict(sorted(outcomes.items())),
        "causal_thread_kinds_observed": dict(sorted(thread_kinds.items())),
        "dynamic_menu_size": {"minimum": min_menu, "maximum": max_menu},
    }
    root = Path(__file__).resolve().parents[1]
    output = root / "docs" / "stress_report_v0_4_0.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
