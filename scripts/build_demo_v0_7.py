from __future__ import annotations

import html
import json
import shutil
from pathlib import Path

from axm_star_sim.atlas import create_revisit_packet, record_visit, register_system_location, revisit_options, verify_visit_chain, write_atlas_files
from axm_star_sim.command_console import render_command_console
from axm_star_sim.contact_horizon import contact_horizon_snapshot, load_contact_horizon_registry
from axm_star_sim.generator import generate_system
from axm_star_sim.io import append_runtime_event, write_system
from axm_star_sim.live_console import render_live_console
from axm_star_sim.runtime import initial_runtime_state, resolve_turn, verify_ledger, verify_recorded_event
from axm_star_sim.technology_core import eligible_core_ids, select_technology_core
from axm_star_sim.thread_engine import build_action_menu


def find_seed(core_id: str) -> str:
    for index in range(100000):
        seed = f"AXM-V07-CORE-{index:05d}"
        selected, _core, _receipt = select_technology_core(seed)
        if selected == core_id:
            return seed
    raise RuntimeError(f"No demonstration seed found for {core_id}")


def representative_action(actions: list[dict]) -> dict:
    for preferred in ("instrument", "patient_observation", "probe", "engineering"):
        for action in actions:
            if action.get("category") == preferred:
                return action
    return actions[0]


def catalog_html(rows: list[dict]) -> str:
    cards = []
    for row in rows:
        known = row["known_parameters"]
        known_html = "".join(
            f'<li><strong>{html.escape(item["id"].replace("_", " "))}</strong>: '
            f'{html.escape(str(item["value"]))} {html.escape(str(item.get("unit") or ""))}</li>'
            for item in known
        ) or "<li>No public numeric performance value in the pinned registry.</li>"
        cards.append(f'''<article class="card">
<h2>{html.escape(row["name"])}</h2>
<p><span class="badge">{html.escape(row["domain"].replace("_", " "))}</span> <span class="badge">{html.escape(row["status"])}</span></p>
<p><strong>Seed-selected slot:</strong> {row["selected_index"] + 1} / {row["eligible_count"]}</p>
<ul>{known_html}</ul>
<p><strong>Unknown parameters preserved:</strong> {row["unknown_count"]}</p>
<p><strong>Physics authority:</strong> transfer values are requirements, not proof of vehicle capability; source-pinned generation only bounds labelled scenarios.</p>
<p><a href="{html.escape(row["core_id"])}/command_console.html">Open command console</a> · <a href="{html.escape(row["core_id"])}/system.html">Open ship/system visualizer</a></p>
</article>''')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AXM v0.7 Factual Technology Core Catalog</title>
<style>
:root{{--bg:#05080d;--panel:#0d1822;--line:#294658;--text:#edf6fa;--muted:#9db1bd;--accent:#72dce9;--warm:#efc77b}}
*{{box-sizing:border-box}} body{{margin:0;background:radial-gradient(circle at top,#102330,#05080d 52%);color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif}}
main{{max-width:1120px;margin:auto;padding:24px}} h1{{font-weight:500;letter-spacing:.08em}} .intro{{color:var(--muted);line-height:1.6;max-width:900px}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:20px}} .card{{background:linear-gradient(180deg,#10202c,var(--panel));border:1px solid var(--line);border-radius:15px;padding:18px}}
h2{{font-size:1.05rem;color:var(--accent)}} li{{margin:.45rem 0}} a{{color:var(--accent)}} .badge{{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:4px 8px;color:var(--warm);font-size:.72rem}}
.callout{{border-left:3px solid var(--warm);padding:10px 14px;background:#0a131b;margin-top:16px;color:var(--muted)}} @media(max-width:760px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<div class="badge">Mike — Axiom/Mir · v0.7.0</div><h1>Factual ship technology cores</h1>
<p class="intro">The seed selects one equal catalog slot. AXM does not rank or manually prefer the technology. Published values remain catalog facts, transparent arithmetic remains derived, operating fractions remain labelled scenarios, and missing mass, thrust, specific impulse, propellant, payload power, or crew data remain blocked.</p>
<div class="callout"><strong>Source-neutral exploration functions:</strong> bridge command, sensors, energy distribution, maneuvering, protection, logistics, fabrication, and immersive visualization can inspire interfaces. Faster-than-light travel, matter teleportation, inertia cancellation, static gravity, force fields, and simulated solid matter never enter the real physics layer.</div>
<div class="grid">{''.join(cards)}</div>
</main></body></html>'''


def prime_long_horizon_state(system: dict) -> dict:
    state = initial_runtime_state(system)
    state["turn"] = 100000
    work = state["contact_horizon"]["scientific_work"]
    work["total_science_actions"] = 1000
    work["independent_observation_context_ids"] = [f"context-{i:02d}" for i in range(12)]
    work["cross_validations"] = 80
    work["false_positive_eliminations"] = 50
    work["passive_search_hours"] = 10000.0
    state["action_menu"] = build_action_menu(system, state)
    return state


def contact_html(registry: dict, locked: dict, eligible: dict, after: dict, event: dict) -> str:
    payload = json.dumps({
        "registry": registry,
        "locked": locked,
        "eligible": eligible,
        "after": after,
        "event": {
            "event_id": event["event_id"],
            "action": event["action"],
            "outcome": event["outcome"],
            "entropy_mode": event["entropy"]["mode"],
            "event_hash": event["event_hash"],
        },
    }, ensure_ascii=False)
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AXM Long Horizon Contact Layer</title><style>
:root{--bg:#05080d;--panel:#0d1822;--line:#294658;--text:#edf6fa;--muted:#9db1bd;--accent:#72dce9;--warm:#efc77b;--danger:#ef9e9e}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#102330,#05080d 55%);color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif}main{max-width:1120px;margin:auto;padding:22px}h1{font-weight:500;letter-spacing:.07em}.lead{max-width:900px;line-height:1.65;color:var(--muted)}.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0}.tabs button{border:1px solid var(--line);background:#0b151e;color:var(--text);padding:9px 12px;border-radius:10px;cursor:pointer}.tabs button.active{border-color:var(--accent);color:var(--accent)}.grid{display:grid;grid-template-columns:1.1fr .9fr;gap:14px}.card{background:linear-gradient(180deg,#10202c,var(--panel));border:1px solid var(--line);border-radius:15px;padding:17px}.metric{display:grid;grid-template-columns:1fr auto;gap:10px;padding:8px 0;border-bottom:1px solid #203441}.metric span{color:var(--muted)}.ladder{display:grid;gap:7px}.rung{padding:10px;border:1px solid var(--line);border-radius:10px;color:var(--muted)}.rung.active{border-color:var(--warm);color:var(--text);background:#17170e}.rung strong{color:var(--accent)}.callout{border-left:3px solid var(--warm);padding:12px 14px;background:#0a131b;color:var(--muted);margin:14px 0}.danger{color:var(--danger)}code{color:var(--accent);word-break:break-all}@media(max-width:800px){.grid{grid-template-columns:1fr}}
</style></head><body><main><div style="color:var(--warm);font-size:.8rem;letter-spacing:.12em">MIKE — AXIOM/MIR · v0.7.0</div><h1>Long Horizon contact layer</h1><p class="lead">Step 100,000 is not an alien encounter. It is the earliest point at which a deeply worked campaign can open dedicated life and technology searches. The master seed contains no hidden species, intention, or contact date.</p><div class="callout"><strong>Factual boundary:</strong> the simulator can generate evidence, uncertainty, theories, instruments, delays, and consequences. It cannot turn a theory into a factual extraterrestrial civilization.</div><div class="tabs"><button data-view="locked">Step 99,999</button><button data-view="eligible">Step 100,000</button><button data-view="after">After first deep search</button></div><div class="grid"><section class="card"><h2 id="phase"></h2><div id="metrics"></div><h3>Claim ceiling</h3><p id="ceiling" class="lead"></p><h3>Demonstration event</h3><div id="event"></div></section><section class="card"><h2>Evidence ladder</h2><div id="ladder" class="ladder"></div></section></div><p class="lead">The first deep-search event is replayable from its recorded deterministic entropy packet. Its result may create a candidate anomaly, but it cannot jump directly to confirmed life, technology, agency, or interaction.</p></main><script>
const data=__PAYLOAD__;let view='locked';const buttons=[...document.querySelectorAll('button[data-view]')];
function metric(k,v){return `<div class="metric"><span>${k}</span><strong>${v}</strong></div>`}
function render(){const s=data[view];buttons.forEach(b=>b.classList.toggle('active',b.dataset.view===view));document.getElementById('phase').textContent=`${s.phase} · evidence stage ${s.evidence_stage}`;document.getElementById('metrics').innerHTML=metric('Current step',s.current_step.toLocaleString())+metric('Steps remaining',s.steps_remaining.toLocaleString())+metric('Search readiness',s.readiness.ready?'READY':'LOCKED')+metric('Confirmed external life',s.confirmed_external_life)+metric('Confirmed external technology',s.confirmed_external_technology)+metric('Confirmed external agency',s.confirmed_external_agency);document.getElementById('ceiling').textContent=s.claim_ceiling;document.getElementById('ladder').innerHTML=data.registry.evidence_ladder.map(r=>`<div class="rung ${r.stage===s.evidence_stage?'active':''}"><strong>${r.stage}. ${r.name}</strong><br>${r.claim_ceiling}</div>`).join('');const e=data.event;document.getElementById('event').innerHTML=view==='after'?metric('Action',e.action)+metric('Outcome',e.outcome.title)+metric('Entropy',e.entropy_mode)+`<p><code>${e.event_hash}</code></p>`:'<p class="lead">No encounter is inserted at this point.</p>'}
buttons.forEach(b=>b.addEventListener('click',()=>{view=b.dataset.view;render()}));render();
</script></body></html>'''.replace('__PAYLOAD__', payload)



def build_persistent_atlas_demo(root: Path) -> dict:
    output = root / "output" / "persistent_atlas_demo"
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    expeditions = []
    for label, seed, turns in (
        ("expedition_alpha", "AXM-V07-ATLAS-ALPHA", 4),
        ("expedition_beta", "AXM-V07-ATLAS-BETA", 3),
    ):
        directory = output / label
        system = generate_system(seed).to_dict()
        write_system(directory, system, "autonomous_deterministic")
        state = initial_runtime_state(system)
        events = []
        for turn in range(turns):
            actions = state["action_menu"]["actions"]
            action = actions[(turn * 2) % len(actions)]["action_id"]
            event, state = resolve_turn(system=system, state=state, action=action, entropy_mode="deterministic")
            append_runtime_event(directory, event, state)
            events.append(event)
        expeditions.append({
            "label": label,
            "directory": directory,
            "system": system,
            "events": events,
            "location_id": json.loads((directory / "expedition_atlas.json").read_text(encoding="utf-8"))["active_location_id"],
        })

    shared = json.loads((expeditions[0]["directory"] / "expedition_atlas.json").read_text(encoding="utf-8"))
    alpha_location_id = expeditions[0]["location_id"]
    shared = register_system_location(shared, expeditions[1]["system"], make_active=True)
    beta_location_id = shared["active_location_id"]
    shared = record_visit(
        shared,
        beta_location_id,
        event=None,
        visit_kind="expedition_transition_arrival",
        note="Second generated expedition branch attached to the persistent crew atlas.",
    )
    for event in expeditions[1]["events"]:
        shared = record_visit(shared, beta_location_id, event)

    packets_dir = output / "revisit_packets"
    packets_dir.mkdir(parents=True, exist_ok=True)
    first_packet, shared = create_revisit_packet(
        shared,
        alpha_location_id,
        "axm-vector-atlas-v0.7",
        "axm-asset-fabric-current",
        camera_language="original-bridge-reconstruction",
    )
    second_packet, shared = create_revisit_packet(
        shared,
        alpha_location_id,
        "future-immersive-visual-engine-v3",
        "future-asset-fabric-v5",
        camera_language="high-fidelity-expedition-reconstruction",
    )
    for packet in (first_packet, second_packet):
        (packets_dir / f"{packet['packet_id']}.json").write_text(
            json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    write_atlas_files(output, shared)
    chain = verify_visit_chain(shared)
    summary = {
        "schema": "axm.v0.7-atlas-demo-summary.v1",
        "status": "PASS" if chain["valid"] else "FAIL",
        "map_id": shared["map_id"],
        "mapped_locations": len(shared["locations"]),
        "routes": len(shared["routes"]),
        "visits": len(shared["visits"]),
        "visit_chain_valid": chain["valid"],
        "alpha_location_id": alpha_location_id,
        "beta_location_id": beta_location_id,
        "revisit_options": revisit_options(shared),
        "revisit_packets": [first_packet["packet_id"], second_packet["packet_id"]],
        "truth_layers": sorted({location["knowledge_class"] for location in shared["locations"].values()}),
    }
    (output / "persistent_atlas_demo.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary

def main() -> int:
    root = Path(__file__).resolve().parents[1]
    output = root / "output"
    output.mkdir(parents=True, exist_ok=True)

    tech_output = output / "technology_core_demo"
    if tech_output.exists():
        shutil.rmtree(tech_output)
    tech_output.mkdir(parents=True)
    rows: list[dict] = []
    for core_id in eligible_core_ids():
        seed = find_seed(core_id)
        system = generate_system(seed).to_dict()
        selected = system["ship"]["technology_core"]
        core_output = tech_output / core_id
        write_system(core_output, system, command_mode="autonomous_deterministic")
        state = json.loads((core_output / "runtime_state.json").read_text(encoding="utf-8"))
        action = representative_action(state["action_menu"]["actions"])
        event, state = resolve_turn(system=system, state=state, action=action["action_id"], entropy_mode="deterministic")
        append_runtime_event(core_output, event, state)
        ledger = [json.loads(line) for line in (core_output / "event_ledger.jsonl").read_text(encoding="utf-8").splitlines() if line]
        valid, checks, _ = verify_ledger(system, ledger)
        if not valid:
            raise AssertionError(checks[-1])
        rows.append({
            "core_id": core_id,
            "seed": seed,
            "name": selected["selected_core"]["name"],
            "domain": selected["selected_core"]["selection"]["domain"],
            "status": selected["selected_core"]["status"]["value"],
            "selected_index": selected["selection_receipt"]["selected_index"],
            "eligible_count": selected["selection_receipt"]["eligible_count"],
            "known_parameters": selected["known_parameter_summary"],
            "unknown_count": len(selected["selected_core"]["unknown_parameters"]),
            "event_hash": event["event_hash"],
            "ledger_valid": valid,
        })
    (tech_output / "catalog.json").write_text(json.dumps({"schema":"axm.v0.7-technology-core-demo.v1","generator_version":"0.6.0","cores":rows}, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    (tech_output / "technology_core_catalog.html").write_text(catalog_html(rows), encoding="utf-8")

    contact_output = output / "contact_horizon_demo"
    if contact_output.exists():
        shutil.rmtree(contact_output)
    campaign_output = contact_output / "campaign"
    contact_system = generate_system("AXM-LONG-HORIZON-FIRST-LIGHT").to_dict()
    write_system(campaign_output, contact_system, command_mode="collaborative_command")
    initial = initial_runtime_state(contact_system)
    initial["turn"] = 99999
    locked = contact_horizon_snapshot(initial)
    ready = prime_long_horizon_state(contact_system)
    eligible = contact_horizon_snapshot(ready)
    contact_action = next(item for item in ready["action_menu"]["actions"] if item["action_id"].startswith("contact-horizon:"))
    event, after_state = resolve_turn(system=contact_system, state=ready, action=contact_action["action_id"], entropy_mode="deterministic")
    check, rebuilt = verify_recorded_event(contact_system, ready, event)
    valid = bool(check["valid"] and rebuilt == after_state)
    if not valid:
        raise AssertionError(check)
    after = contact_horizon_snapshot(after_state)
    campaign_output.mkdir(parents=True, exist_ok=True)
    (campaign_output / "runtime_state.json").write_text(json.dumps(after_state, indent=2, ensure_ascii=False), encoding="utf-8")
    (campaign_output / "event_ledger.jsonl").write_text(json.dumps(event, ensure_ascii=False)+"\n", encoding="utf-8")
    (campaign_output / "command_console.html").write_text(render_command_console(contact_system, after_state, [event], None), encoding="utf-8")
    (campaign_output / "adventure_console.html").write_text(render_live_console(contact_system, after_state, [event]), encoding="utf-8")
    registry = load_contact_horizon_registry()
    summary = {"schema":"axm.v0.7-contact-horizon-demo.v1","locked":locked,"eligible":eligible,"after_first_search":after,"event":event,"ledger_valid":valid}
    contact_output.mkdir(parents=True, exist_ok=True)
    (contact_output / "contact_horizon_demo.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    (contact_output / "contact_horizon_console.html").write_text(contact_html(registry, locked, eligible, after, event), encoding="utf-8")

    atlas_demo = build_persistent_atlas_demo(root)

    print(json.dumps({
        "status": "demo_built",
        "persistent_atlas_demo": atlas_demo,
        "technology_cores": len(rows),
        "contact_unlock_step": registry["unlock_step"],
        "contact_event_replay_valid": valid,
        "contact_stage_after_first_search": after["evidence_stage"],
        "open": [
            str(root / "output" / "persistent_atlas_demo" / "atlas.html"),
            str(root / "output" / "persistent_atlas_demo" / "expedition_alpha" / "command_console.html"),
            str(root / "output" / "persistent_atlas_demo" / "expedition_beta" / "command_console.html"),
            str(tech_output / "technology_core_catalog.html"),
            str(contact_output / "contact_horizon_console.html"),
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
