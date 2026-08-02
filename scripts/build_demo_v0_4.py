from __future__ import annotations

import json
import shutil
from pathlib import Path

from axm_star_sim.generator import generate_system
from axm_star_sim.io import append_runtime_event, write_system
from axm_star_sim.runtime import resolve_turn, verify_ledger


def choose(rows: list[dict], predicate) -> dict:
    for row in rows:
        if predicate(row):
            return row
    return rows[0]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    output = root / "output" / "physics_threads_demo"
    if output.exists():
        shutil.rmtree(output)
    system = generate_system("AXM-PROBE-0").to_dict()
    write_system(output, system, command_mode="autonomous_deterministic")
    state = json.loads((output / "runtime_state.json").read_text(encoding="utf-8"))

    actions = state["action_menu"]["actions"]
    launch = choose(actions, lambda row: row["category"] == "probe" and not row.get("parameters", {}).get("wait_for_probe"))
    event, state = resolve_turn(system=system, state=state, action=launch["action_id"], entropy_mode="deterministic")
    append_runtime_event(output, event, state)

    for turn in range(4):
        actions = state["action_menu"]["actions"]
        follow = choose(
            actions,
            lambda row: (
                "probe" in row["label"].lower()
                or "telemetry" in row["label"].lower()
                or row.get("source_thread") in {"probe-in-flight", "communication-latency"}
            ),
        )
        event, state = resolve_turn(system=system, state=state, action=follow["action_id"], entropy_mode="deterministic")
        append_runtime_event(output, event, state)

    ledger = [json.loads(line) for line in (output / "event_ledger.jsonl").read_text(encoding="utf-8").splitlines() if line]
    valid, checks, _ = verify_ledger(system, ledger)
    if not valid:
        raise AssertionError(checks[-1])
    print(json.dumps({
        "status": "demo_built",
        "output": str(output),
        "events": len(ledger),
        "ledger_valid": valid,
        "active_threads": state["action_menu"]["active_thread_ids"],
        "action_count": len(state["action_menu"]["actions"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
