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


def contact_html(registry: dict, locked: dict, eligible: dict, after: dict, event: dict, next_actions: list[dict]) -> str:
    payload = json.dumps({
        "registry": registry,
        "locked": locked,
        "eligible": eligible,
        "after": after,
        "event": {
            "event_id": event["event_id"],
            "action": event["action"],
            "intent": event.get("action_record", {}).get("intent", ""),
            "outcome": event["outcome"],
            "entropy_mode": event["entropy"]["mode"],
            "event_hash": event["event_hash"],
        },
        "next_actions": [
            {
                "action_id": action["action_id"],
                "label": action["label"],
                "category": action["category"],
                "intent": action.get("intent", ""),
            }
            for action in next_actions[:4]
        ],
    }, ensure_ascii=False)
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AXM Long Horizon Contact Layer</title><style>
:root{--bg:#05080d;--panel:#0d1822;--line:#294658;--text:#edf6fa;--muted:#9db1bd;--accent:#72dce9;--warm:#efc77b;--danger:#ef9e9e;--ok:#8be0b1}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#102330,#05080d 55%);color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif}main{max-width:1180px;margin:auto;padding:22px}h1{font-weight:500;letter-spacing:.07em;margin-bottom:.35rem}h2{font-weight:600}h3{font-size:.78rem;letter-spacing:.12em;text-transform:uppercase;color:var(--warm);margin:18px 0 9px}.lead{max-width:920px;line-height:1.65;color:var(--muted)}.truthbar{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.truthbar span{border:1px solid var(--line);border-radius:999px;padding:6px 9px;font-size:.72rem;letter-spacing:.08em}.truthbar .hold{border-color:#7d5f37;color:var(--warm)}.checkpoint-shell{margin:20px 0 15px}.checkpoint-label{font-size:.72rem;letter-spacing:.12em;color:var(--muted);text-transform:uppercase;margin-bottom:7px}.tabs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.tabs button{min-height:48px;border:1px solid var(--line);background:#0b151e;color:var(--text);padding:9px 12px;border-radius:10px;cursor:pointer;text-align:left}.tabs button small{display:block;color:var(--muted);margin-top:4px}.tabs button[aria-selected="true"]{border-color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent);color:var(--accent);background:#0c2028}.tabs button:focus-visible{outline:3px solid var(--warm);outline-offset:3px}.grid{display:grid;grid-template-columns:1.12fr .88fr;gap:14px;align-items:start}.card{background:linear-gradient(180deg,#10202c,var(--panel));border:1px solid var(--line);border-radius:15px;padding:17px;min-width:0}.metric{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;padding:8px 0;border-bottom:1px solid #203441}.metric span{color:var(--muted)}.ceiling{border-left:3px solid var(--warm);padding:12px 14px;background:#0a131b;color:var(--text);line-height:1.55}.readiness{display:grid;gap:7px}.check{display:grid;grid-template-columns:auto 1fr;gap:9px;align-items:start;border:1px solid var(--line);border-radius:10px;padding:9px}.check b{font-size:.72rem;min-width:43px}.check.pass b{color:var(--ok)}.check.hold b{color:var(--danger)}.check span{color:var(--muted);font-size:.86rem;line-height:1.35}.candidate{display:flex;gap:7px;flex-wrap:wrap}.candidate span{border:1px solid var(--line);border-radius:999px;padding:5px 8px;color:var(--muted);font-size:.76rem}.actions{display:grid;gap:8px}.action{border:1px solid var(--line);border-radius:11px;padding:10px;background:#0a131b}.action strong{display:block;color:var(--accent);margin-bottom:4px}.action p{margin:0;color:var(--muted);line-height:1.4;font-size:.88rem}.action code{display:block;margin-top:5px;color:#7fa2b5;font-size:.68rem;word-break:break-all}.ladder{display:grid;gap:7px}.rung{padding:10px;border:1px solid var(--line);border-radius:10px;color:var(--muted)}.rung.active{border-color:var(--warm);color:var(--text);background:#17170e}.rung strong{color:var(--accent)}.event{margin-top:10px}.boundary{border-left:3px solid var(--warm);padding:12px 14px;background:#0a131b;color:var(--muted);margin:14px 0}code{color:var(--accent);word-break:break-all}.sr-status{position:relative;border:1px solid var(--line);border-radius:10px;padding:9px 11px;color:var(--muted);font-size:.82rem;margin:10px 0 0}.sr-status strong{color:var(--text)}
@media(max-width:800px){main{padding:16px}.grid{grid-template-columns:1fr}.tabs{display:flex;overflow-x:auto;scroll-snap-type:x proximity;padding-bottom:4px}.tabs button{flex:0 0 min(79vw,280px);scroll-snap-align:start}.metric{grid-template-columns:1fr}.metric strong{text-align:left}.card{padding:14px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}
@media(prefers-contrast:more){:root{--line:#6f96aa;--muted:#c1d0d8}.card,.tabs button,.check,.action{border-width:2px}}
</style></head><body><main><div style="color:var(--warm);font-size:.8rem;letter-spacing:.12em">MIKE — AXIOM/MIR · v0.7.0</div><h1>Long Horizon contact layer</h1><p class="lead">Step 100,000 is not an alien encounter. It is the earliest point at which a deeply worked campaign can open dedicated life and technology searches. The master seed contains no hidden species, intention, or contact date.</p><div class="truthbar"><span>LOCAL RECEIPT VIEW</span><span>DISPLAY ≠ DISCOVERY</span><span class="hold">SEARCH READINESS ≠ CONTACT</span></div><div class="boundary"><strong>Factual boundary:</strong> the simulator can generate evidence, uncertainty, theories, instruments, delays, and consequences. It cannot turn a theory into a factual extraterrestrial civilization.</div><section class="checkpoint-shell"><div class="checkpoint-label">Recorded campaign checkpoints · inspect only</div><div class="tabs" role="tablist" aria-label="Recorded Contact Horizon checkpoints"><button role="tab" id="tab-locked" aria-controls="checkpoint" aria-selected="true" tabindex="0" data-view="locked">Step 99,999<small>readiness held</small></button><button role="tab" id="tab-eligible" aria-controls="checkpoint" aria-selected="false" tabindex="-1" data-view="eligible">Step 100,000<small>eligibility boundary</small></button><button role="tab" id="tab-after" aria-controls="checkpoint" aria-selected="false" tabindex="-1" data-view="after">First deep search<small>recorded result</small></button></div><div id="liveStatus" class="sr-status" role="status" aria-live="polite"></div></section><div class="grid"><section id="checkpoint" role="tabpanel" aria-labelledby="tab-locked" class="card"><h2 id="phase"></h2><div id="metrics"></div><h3>Current claim ceiling</h3><p id="ceiling" class="ceiling"></p><h3>Readiness gate</h3><div id="readiness" class="readiness"></div><div id="candidateWrap" hidden><h3>Candidate classes still open</h3><div id="candidate" class="candidate"></div></div><h3>Next scientific move</h3><div id="actions" class="actions"></div><h3>Demonstration event</h3><div id="event" class="event"></div></section><section class="card"><h2>Evidence ladder</h2><p class="lead">The highlight is the recorded stage at this checkpoint. Higher rungs remain definitions, not predictions.</p><div id="ladder" class="ladder"></div></section></div><p class="lead">The first deep-search event is replayable from its recorded deterministic entropy packet. Its result may create a candidate anomaly, but it cannot jump directly to confirmed life, technology, agency, or interaction.</p></main><script>
const data=__PAYLOAD__;let view='locked';const order=['locked','eligible','after'];const buttons=[...document.querySelectorAll('button[data-view]')];
const checkLabels={step_reached:['Step boundary','step 100,000 reached'],science_actions:['Science depth','minimum science actions satisfied'],independent_observation_contexts:['Independent contexts','independent observation contexts satisfied'],cross_validations:['Cross-validation','cross-validation floor satisfied'],false_positive_eliminations:['False-positive work','false-positive elimination floor satisfied'],passive_search_hours:['Passive search','passive search duration satisfied']};
const esc=value=>String(value??'').replace(/[&<>\"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[ch]));
function metric(k,v){return `<div class="metric"><span>${esc(k)}</span><strong>${esc(v)}</strong></div>`}
function renderReadiness(s){return Object.entries(s.readiness.checks).map(([key,passed])=>{const label=checkLabels[key]||[key,key];return `<div class="check ${passed?'pass':'hold'}"><b>${passed?'PASS':'HOLD'}</b><span><strong>${esc(label[0])}</strong><br>${esc(label[1])}</span></div>`}).join('')}
function renderActions(){if(view==='locked')return '<div class="action"><strong>Deep search held</strong><p>The recorded readiness checks are not satisfied, so this checkpoint admits no deep-search action.</p></div>';if(view==='eligible')return `<div class="action"><strong>${esc(data.event.action)}</strong><p>${esc(data.event.intent||'Recorded demonstration action at the eligibility boundary.')}</p><code>${esc(data.event.event_id)}</code></div>`;if(!data.next_actions.length)return '<div class="action"><strong>No later action in this demo receipt</strong><p>The observer will not invent a continuation.</p></div>';return data.next_actions.map(a=>`<div class="action"><strong>${esc(a.label)}</strong><p>${esc(a.intent||a.category)}</p><code>${esc(a.action_id)}</code></div>`).join('')}
function render(){const s=data[view];buttons.forEach(b=>{const active=b.dataset.view===view;b.setAttribute('aria-selected',String(active));b.tabIndex=active?0:-1});const panel=document.getElementById('checkpoint');panel.setAttribute('aria-labelledby',`tab-${view}`);document.getElementById('phase').textContent=`${s.evidence_stage_name} · stage ${s.evidence_stage}`;document.getElementById('metrics').innerHTML=metric('Current step',s.current_step.toLocaleString())+metric('Search readiness',s.readiness.ready?'READY — ELIGIBLE TO SEARCH':'HELD — SEARCH NOT ADMITTED')+metric('Candidate',s.candidate_id||'none')+metric('External life confirmed',s.confirmed_external_life?'yes':'no')+metric('External technology confirmed',s.confirmed_external_technology?'yes':'no')+metric('External agency confirmed',s.confirmed_external_agency?'yes':'no');document.getElementById('ceiling').textContent=s.claim_ceiling;document.getElementById('readiness').innerHTML=renderReadiness(s);const candidateWrap=document.getElementById('candidateWrap');candidateWrap.hidden=!s.candidate_classes.length;document.getElementById('candidate').innerHTML=s.candidate_classes.map(c=>`<span>${esc(c.id)} · ${esc(c.status)}</span>`).join('');document.getElementById('actions').innerHTML=renderActions();document.getElementById('ladder').innerHTML=data.registry.evidence_ladder.map(r=>`<div class="rung ${r.stage===s.evidence_stage?'active':''}"><strong>${esc(r.stage)}. ${esc(r.name)}</strong><br>${esc(r.claim_ceiling)}</div>`).join('');const e=data.event;document.getElementById('event').innerHTML=view==='after'?metric('Action',e.action)+metric('Outcome',e.outcome.title)+metric('Entropy',e.entropy_mode)+`<p><code>${esc(e.event_hash)}</code></p>`:'<p class="lead">No encounter is inserted at this checkpoint.</p>';document.getElementById('liveStatus').innerHTML=`<strong>${esc(buttons.find(b=>b.dataset.view===view).textContent.trim())}</strong> · ${s.readiness.ready?'search ready':'search held'} · evidence stage ${esc(s.evidence_stage)} · external life confirmed: ${s.confirmed_external_life?'yes':'no'}`}
function select(next,focus=false){view=next;render();if(focus)buttons[order.indexOf(view)].focus()}
buttons.forEach((b,index)=>{b.addEventListener('click',()=>select(b.dataset.view));b.addEventListener('keydown',event=>{let target=null;if(event.key==='ArrowRight')target=(index+1)%buttons.length;if(event.key==='ArrowLeft')target=(index-1+buttons.length)%buttons.length;if(event.key==='Home')target=0;if(event.key==='End')target=buttons.length-1;if(target!==null){event.preventDefault();select(buttons[target].dataset.view,true)}})});render();
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
    (contact_output / "contact_horizon_console.html").write_text(contact_html(registry, locked, eligible, after, event, after_state["action_menu"]["actions"]), encoding="utf-8")

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
