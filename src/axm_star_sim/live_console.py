from __future__ import annotations

import html
import json
from typing import Any

from .runtime import preview_turn


def render_live_console(system: dict[str, Any], state: dict[str, Any], ledger: list[dict[str, Any]]) -> str:
    action_records = list((state.get("action_menu") or {}).get("actions", []))
    previews = {item["action_id"]: preview_turn(system, state, item["action_id"]) for item in action_records}
    system_payload = json.dumps(system, ensure_ascii=False).replace("</", "<\\/")
    state_payload = json.dumps(state, ensure_ascii=False).replace("</", "<\\/")
    ledger_payload = json.dumps(ledger, ensure_ascii=False).replace("</", "<\\/")
    action_payload = json.dumps(action_records, ensure_ascii=False).replace("</", "<\\/")
    preview_payload = json.dumps(previews, ensure_ascii=False).replace("</", "<\\/")
    title = html.escape(system["name"])
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Physics-Coupled Open Future Console</title>
<style>
:root{{--bg:#05080d;--panel:#0a141d;--panel2:#0e1b26;--line:#294658;--text:#eaf4fa;--muted:#8fa8b8;--accent:#6ed8e8;--warm:#f2c879;--good:#88e2a4;--warn:#ffcf73}}
*{{box-sizing:border-box}} body{{margin:0;background:radial-gradient(circle at 50% 0,#0d1b27,#05080d 55%);color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif}}
main{{max-width:1180px;margin:auto;padding:18px}} header{{border-bottom:1px solid var(--line);padding-bottom:14px;margin-bottom:14px}}
h1{{margin:4px 0;font-size:clamp(1.4rem,4vw,2.5rem);font-weight:500;letter-spacing:.08em}} .kicker{{color:var(--warm);letter-spacing:.22em;text-transform:uppercase;font-size:.72rem}}
.grid{{display:grid;grid-template-columns:1.05fr .95fr;gap:12px}} .panel{{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);border-radius:14px;padding:14px}}
h2{{font-size:.78rem;color:var(--accent);letter-spacing:.14em;text-transform:uppercase;margin:0 0 10px}} label{{display:block;color:var(--muted);margin:10px 0 5px}}
select,button{{width:100%;padding:11px;border:1px solid var(--line);border-radius:9px;background:#0c202d;color:var(--text);font:inherit}} button{{cursor:pointer;margin-top:10px}} button:hover{{border-color:var(--accent)}}
.note{{color:var(--muted);font-size:.86rem;line-height:1.5}} .contract{{border-left:3px solid var(--good);padding-left:10px}} .result{{border-left:3px solid var(--warm);padding-left:12px;min-height:130px}}
.readout{{display:flex;justify-content:space-between;gap:12px;padding:7px 0;border-bottom:1px solid rgba(41,70,88,.5)}} .readout span{{color:var(--muted)}}
.badge{{display:inline-block;border:1px solid currentColor;border-radius:999px;padding:3px 8px;font-size:.7rem;color:var(--accent)}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#050b10;border:1px solid var(--line);border-radius:10px;padding:10px;max-height:300px;overflow:auto;font-size:.75rem}}
.timeline{{margin-top:12px}} .event{{border-bottom:1px solid var(--line);padding:10px 0}} .event strong{{color:var(--warm)}}
@media(max-width:780px){{.grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body><main>
<header><div class="kicker">AXM factual star adventure simulator · v0.6 source-pinned ship core + physics-coupled open future</div><h1>{title}</h1><div class="note">The Python runtime generates the action menu from live causal threads, calculates the complete physics expectation, and only then resolves uncertainty. This browser lab uses the same exported pre-entropy snapshots for a portable one-step demonstration.</div></header>
<div class="grid">
<section class="panel"><h2>Live decision</h2>
<div class="contract note"><strong>Unresolved future:</strong> physics and probability are visible now, but no outcome is selected until Resolve is pressed.</div>
<label for="action">Generated causal action</label><select id="action"></select>
<label for="mode">Resolution mode</label><select id="mode"><option value="browser_live">Browser live entropy</option><option value="mixed_live">Seed + browser live entropy</option><option value="deterministic">Deterministic replay/test</option></select>
<button id="resolve" type="button">Resolve from this physics snapshot</button><button id="export" type="button">Export browser event ledger</button>
<p id="status" class="note" aria-live="polite"></p>
</section>
<section class="panel"><h2>Pre-entropy physics expectation</h2><div id="physics"></div></section>
<section class="panel"><h2>Current ship state</h2><div id="resources"></div></section>
<section class="panel"><h2>Factual technology core</h2><div id="technology"></div></section>
<section class="panel"><h2>Resolved event</h2><div id="result" class="result note">No future event has been resolved in this browser session.</div></section>
<section class="panel"><h2>Entropy + physics receipt</h2><pre id="receipt">Waiting for an event.</pre></section>
<section class="panel"><h2>Current causal menu</h2><div id="threads" class="note"></div></section>
</div>
<section class="panel timeline"><h2>Browser timeline</h2><div id="timeline"></div></section>
<section class="panel timeline"><h2>Authority boundary</h2><p class="note">Browser events are portable experiments. Only the Python CLI evolves the authoritative causal threads, regenerates the next action menu, updates probe trajectories, and writes the replay-verifiable event chain.</p></section>
<script>
const system={system_payload};
let state={state_payload};
let ledger={ledger_payload};
const actionRecords={action_payload};
const previews={preview_payload};
const actionEl=document.getElementById('action');
actionRecords.forEach((a,i)=>{{const o=document.createElement('option');o.value=a.action_id;o.textContent=`${{i+1}}. ${{a.label}}`;actionEl.appendChild(o)}});
function enc(s){{return new TextEncoder().encode(s)}}
function hex(buf){{return [...new Uint8Array(buf)].map(b=>b.toString(16).padStart(2,'0')).join('')}}
async function sha(s){{if(!crypto.subtle)throw new Error('Web Crypto digest unavailable; use the Python CLI.');return hex(await crypto.subtle.digest('SHA-256',enc(s)))}}
function secureToken(){{if(!crypto.getRandomValues)throw new Error('Secure browser entropy unavailable; use the Python CLI.');const a=new Uint8Array(32);crypto.getRandomValues(a);return hex(a)}}
function current(){{return previews[actionEl.value]}}
function renderResources(){{const r=state.resources;document.getElementById('resources').innerHTML=Object.entries(r).map(([k,v])=>`<div class="readout"><span>${{k.replaceAll('_',' ')}}</span><strong>${{v}}</strong></div>`).join('')+`<div class="readout"><span>turn</span><strong>${{state.turn}}</strong></div>`}}
function renderTechnology(){{const t=system.ship?.technology_core;if(!t){{document.getElementById('technology').innerHTML='<div class="note">No source-pinned technology profile is present.</div>';return}}const c=t.selected_core,known=t.known_parameter_summary||[],blocked=t.blocked_calculations||[];const rows=known.length?known.map(k=>`<div class="readout"><span>${{k.id.replaceAll('_',' ')}}</span><strong>${{k.value}} ${{k.unit||''}}</strong></div>`).join(''):'<div class="note">No public numeric performance value is available in the pinned sources.</div>';document.getElementById('technology').innerHTML=`<div class="readout"><span>selected lineage</span><strong>${{c.name}}</strong></div><div class="readout"><span>core class</span><strong>${{c.core_class.replaceAll('_',' ')}}</strong></div><div class="readout"><span>catalog slot</span><strong>${{t.selection_receipt.selected_index+1}} / ${{t.selection_receipt.eligible_count}}</strong></div>${{rows}}<p class="note"><strong>Unknowns stay unknown:</strong> ${{c.unknown_parameters.length}} blocked parameters. No manual technology preference or fictional performance is used.</p><p class="note">Blocked calculations: ${{[...new Set(blocked.map(b=>b.quantity))].join(', ')}}</p>`}}
function renderPhysics(){{const x=current(),p=x.physics_expectation,a=x.action_record;document.getElementById('physics').innerHTML=`<div class="readout"><span>target</span><strong>${{p.target_planet_name}}</strong></div><div class="readout"><span>source thread</span><strong>${{a.source_thread}}</strong></div><div class="readout"><span>orbital phase</span><strong>${{p.orbital_state.true_anomaly_deg.toFixed(2)}}°</strong></div><div class="readout"><span>star distance</span><strong>${{p.orbital_state.star_distance_au.toFixed(4)}} AU</strong></div><div class="readout"><span>expected SNR</span><strong>${{p.sensor.expected_snr.toFixed(2)}}</strong></div><div class="readout"><span>thermal ratio</span><strong>${{p.thermal.thermal_load_ratio.toFixed(3)}}</strong></div><div class="readout"><span>radiation risk</span><strong>${{p.radiation.shielded_risk_index.toFixed(3)}}</strong></div><div class="readout"><span>one-way delay</span><strong>${{p.communications.one_way_light_time_s.toFixed(1)}} s</strong></div><div class="readout"><span>reference transfer</span><strong>${{p.trajectory.transfer_time_days.toFixed(2)}} d</strong></div>`}}
function renderThreads(){{document.getElementById('threads').innerHTML=`<p><strong>${{state.action_menu.active_thread_ids.length}}</strong> active threads generated this menu.</p>`+actionRecords.map(a=>`<div class="event"><span class="badge">${{a.category}}</span> <strong>${{a.label}}</strong><div>${{a.intent}}</div></div>`).join('')}}
function renderTimeline(){{document.getElementById('timeline').innerHTML=ledger.length?ledger.map(e=>`<div class="event"><span class="badge">${{e.entropy?.mode||e.entropy_mode}}</span> <strong>Turn ${{e.turn}} · ${{e.outcome.title}}</strong><div class="note">${{e.action}}</div></div>`).join(''):'<div class="note">No browser events yet.</div>'}}
function choose(rows,v){{let c=0;for(const o of rows){{c+=o.probability;if(v<=c)return o}}return rows.at(-1)}}
function confidence(snr){{return snr>=8?'strong':snr>=5?'moderate':snr>=3?'candidate':'below-detection-threshold'}}
function observation(out,p,snr,channel){{const phase=p.orbital_state.true_anomaly_deg.toFixed(2),target=p.target_planet_name;if(out.id==='clear-evidence')return `At orbital phase ${{phase}}°, the ${{channel}} measurement of ${{target}} repeats with realized SNR ${{snr.toFixed(2)}}.`;if(out.id==='ambiguous-evidence')return `The ${{channel}} reaches SNR ${{snr.toFixed(2)}}, but remains compatible with multiple physical explanations.`;if(out.id==='unexpected-coupling')return `The ${{channel}} changes with orbital geometry, thermal load, or the radiation channel, opening a new causal thread.`;if(out.id==='operational-complication')return `Thermal ratio ${{p.thermal.thermal_load_ratio.toFixed(3)}}, radiation risk ${{p.radiation.shielded_risk_index.toFixed(3)}}, and communication delay constrain the attempt.`;return `Nothing in the ${{channel}} exceeds the current detection threshold at orbital phase ${{phase}}°.`}}
function applyPreview(p,out){{state.turn+=1;state.mission_time_hours+=p.expected_duration_hours;const r=state.resources;r.knowledge_points=Math.max(0,(r.knowledge_points||0)+(out.id==='clear-evidence'?12:out.id==='unexpected-coupling'?10:out.id==='ambiguous-evidence'?6:out.id==='quiet-constraint'?4:3));r.heat_percent=Math.max(0,Math.min(100,r.heat_percent+(p.thermal.thermal_load_ratio-.72)*8));r.reactor_reserve_percent=Math.max(0,r.reactor_reserve_percent-Math.min(8,p.configuration.instrument_power_kw*p.expected_duration_hours/60))}}
actionEl.addEventListener('change',renderPhysics);
document.getElementById('resolve').addEventListener('click',async()=>{{const status=document.getElementById('status');try{{status.textContent='Resolving…';const x=current(),p=x.physics_expectation,a=x.action_record,mode=document.getElementById('mode').value;const context=JSON.stringify({{system_id:system.system_id,turn:state.turn+1,action_id:a.action_id,physics_sha256:x.physics_expectation_sha256,previous:ledger.at(-1)?.event_hash??null}});const deterministic=await sha('AXM-BROWSER-DETERMINISTIC-V2|'+system.master_seed+'|'+context);let live=null,combined;if(mode==='deterministic')combined=await sha(deterministic);else{{live=secureToken();combined=await sha(mode+'|'+deterministic+'|'+live)}}const rollHex=await sha(combined+'|outcome'),noiseHex=await sha(combined+'|sensor-noise'),detailHex=await sha(combined+'|measurement-detail');const v=parseInt(rollHex.slice(0,13),16)/0x1fffffffffffff,noise=parseInt(noiseHex.slice(0,13),16)/0x1fffffffffffff,detail=parseInt(detailHex.slice(0,13),16)/0x1fffffffffffff;const out=choose(x.probability_snapshot,v);const snr=Math.max(0,p.sensor.expected_snr*(1+(noise-.5)*.36));const channels=['spectral slope','timing drift','polarization channel','thermal response','orbital-phase correlation','instrument cross-calibration','radiation coincidence channel','probe range-rate'];const channel=channels[Math.min(channels.length-1,Math.floor(detail*channels.length))];applyPreview(p,out);const event={{schema:'axm.browser-physics-event.v2',turn:state.turn,action:a.label,action_id:a.action_id,entropy_mode:mode,predetermined_by_master_seed:mode==='deterministic',physics_expectation:p,probability_snapshot:x.probability_snapshot,outcome:{{...out,title:out.title,observation:observation(out,p,snr,channel),measurement:{{expected_snr:p.sensor.expected_snr,realized_snr:snr,confidence_band:confidence(snr),detail_channel:channel}}}},rolls:{{outcome:v,sensor_noise:noise,measurement_detail:detail}},entropy:{{context_sha256:await sha(context),combined_sha256:combined,local_token_hex:live}},resolved_at:new Date().toISOString()}};event.event_hash=await sha(JSON.stringify(event));ledger.push(event);document.getElementById('result').innerHTML=`<h3>${{out.title}}</h3><p>${{event.outcome.observation}}</p><p><span class="badge">${{event.outcome.measurement.confidence_band}}</span> This result was selected only after the physics expectation was fixed.</p>`;document.getElementById('receipt').textContent=JSON.stringify({{physics_expectation_sha256:x.physics_expectation_sha256,entropy:event.entropy,rolls:event.rolls,probabilities:x.probability_snapshot}},null,2);status.textContent=mode==='deterministic'?'Resolved deterministically for replay/testing.':'Resolved using entropy sampled after the action and physics snapshot.';renderResources();renderTimeline()}}catch(err){{status.textContent=err.message}}}});
document.getElementById('export').addEventListener('click',()=>{{const blob=new Blob([JSON.stringify({{system_id:system.system_id,state,ledger}},null,2)],{{type:'application/json'}});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`AXM_${{system.system_id}}_browser_physics_ledger.json`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}});
renderResources();renderTechnology();renderPhysics();renderThreads();renderTimeline();
</script></main></body></html>'''
