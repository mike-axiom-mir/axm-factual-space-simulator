from __future__ import annotations

import html
import json
from typing import Any

from .command import crew_assessment, mode_catalog
from .runtime import preview_turn


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def render_command_console(
    system: dict[str, Any],
    state: dict[str, Any],
    ledger: list[dict[str, Any]],
    pending_session: dict[str, Any] | None = None,
) -> str:
    assessment = crew_assessment(system, state)
    action_records = list((state.get("action_menu") or {}).get("actions", []))
    previews = {
        item["action_id"]: preview_turn(system, state, item["action_id"])
        for item in action_records
    }
    title = html.escape(system["name"])
    payloads = {
        "__SYSTEM__": _safe_json(system),
        "__STATE__": _safe_json(state),
        "__LEDGER__": _safe_json(ledger),
        "__MODES__": _safe_json(mode_catalog()),
        "__ASSESSMENT__": _safe_json(assessment),
        "__PENDING__": _safe_json(pending_session),
        "__ACTION_RECORDS__": _safe_json(action_records),
        "__PREVIEWS__": _safe_json(previews),
        "__TITLE__": title,
    }
    page = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ — Four Command Modes</title>
<style>
:root{--bg:#05080d;--panel:#0a141d;--panel2:#0e1b26;--line:#294658;--text:#eaf4fa;--muted:#90a8b7;--accent:#6ed8e8;--warm:#f2c879;--good:#88e2a4;--warn:#ffb978;--bad:#ff8f8f}
*{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at 50% 0,#102130,#05080d 58%);color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif}
main{max-width:1200px;margin:auto;padding:18px} header{border-bottom:1px solid var(--line);padding-bottom:14px;margin-bottom:14px}
h1{margin:4px 0;font-size:clamp(1.5rem,4vw,2.7rem);font-weight:500;letter-spacing:.07em}.kicker{color:var(--warm);letter-spacing:.22em;text-transform:uppercase;font-size:.72rem}.note{color:var(--muted);line-height:1.5;font-size:.88rem}
.mode-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}.mode{border:1px solid var(--line);border-radius:13px;padding:12px;background:linear-gradient(180deg,var(--panel2),var(--panel));min-height:180px}.mode.active{border-color:var(--good);box-shadow:inset 0 0 0 1px var(--good)}.number{color:var(--warm);font-size:1.5rem}.mode h2{font-size:.95rem;margin:6px 0}.badge{display:inline-block;border:1px solid currentColor;border-radius:999px;padding:3px 8px;font-size:.7rem;color:var(--accent)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.panel{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);border-radius:14px;padding:14px}.panel h2{font-size:.78rem;color:var(--accent);letter-spacing:.14em;text-transform:uppercase;margin:0 0 10px}
.action{border-bottom:1px solid rgba(41,70,88,.6);padding:10px 0}.bar{height:8px;background:#071018;border-radius:999px;overflow:hidden;margin-top:6px}.bar span{display:block;height:100%;background:var(--accent)}.vote{padding:7px 0;border-bottom:1px solid rgba(41,70,88,.5)}
label{display:block;color:var(--muted);margin:10px 0 5px} select,textarea,button{width:100%;padding:10px;border:1px solid var(--line);border-radius:9px;background:#0c202d;color:var(--text);font:inherit}textarea{min-height:76px;resize:vertical}button{cursor:pointer;margin-top:9px}button:hover{border-color:var(--accent)}
.split{display:grid;grid-template-columns:1fr 1fr;gap:10px}.status{border-left:3px solid var(--warm);padding:10px;margin-top:10px;min-height:65px}.discussion{max-height:280px;overflow:auto}.message{padding:9px;border-bottom:1px solid var(--line)}.message strong{color:var(--warm)}.timeline{margin-top:12px}.event{padding:10px 0;border-bottom:1px solid var(--line)}
.warning{color:var(--warn)}.good{color:var(--good)}.bad{color:var(--bad)}
@media(max-width:900px){.mode-grid{grid-template-columns:1fr 1fr}}@media(max-width:680px){.grid,.split,.mode-grid{grid-template-columns:1fr}}
</style>
</head>
<body><main>
<header><div class="kicker">AXM factual star adventure simulator · v0.6 factual technology-core command architecture</div><h1>__TITLE__</h1><div class="note">One deterministic crew. Four explicit authority modes. No silent commander switch and no hidden tie-break in collaboration mode.</div></header>
<section id="modes" class="mode-grid"></section>
<div class="grid">
<section class="panel"><h2>Deterministic crew assessment</h2><div id="recommendation"></div><div id="actions"></div></section>
<section class="panel"><h2>Crew seat votes</h2><div id="votes"></div></section>
<section class="panel"><h2>Pre-entropy physics expectation</h2><div id="physics" class="note"></div></section>
<section class="panel"><h2>Human + AI command council</h2>
<div class="split"><div><label for="humanAction">Human vote</label><select id="humanAction"></select><label for="humanWhy">Human reasoning</label><textarea id="humanWhy" placeholder="What matters, what risk is acceptable, and why?"></textarea></div>
<div><label for="aiAction">AI vote</label><select id="aiAction"></select><label for="aiWhy">AI reasoning</label><textarea id="aiWhy" placeholder="Paste or enter the AI command rationale here."></textarea></div></div>
<button id="compare" type="button">Compare command votes</button><div id="status" class="status note" aria-live="polite"></div>
<label for="speaker">Discussion speaker</label><select id="speaker"><option value="human">Human</option><option value="ai">AI</option></select>
<label for="message">Discussion message</label><textarea id="message" placeholder="Challenge assumptions, answer concerns, or propose a compromise."></textarea>
<button id="addMessage" type="button">Add discussion message</button><button id="export" type="button">Export council packet</button>
</section>
<section class="panel"><h2>Discussion transcript</h2><div id="discussion" class="discussion note"></div></section>
</div>
<section class="panel timeline"><h2>Resolved command timeline</h2><div id="timeline"></div></section>
<section class="panel timeline"><h2>Factual ship technology core</h2><div id="technology"></div></section>
<section class="panel timeline"><h2>Authority boundary</h2><p class="note">This browser console drafts and exports command packets. The Python runtime remains authoritative: it validates actions, stores pending disagreement sessions, records command hashes inside resolved events, and verifies the replay chain.</p></section>
<script>
const system=__SYSTEM__;
const state=__STATE__;
const ledger=__LEDGER__;
const modes=__MODES__;
const assessment=__ASSESSMENT__;
const pending=__PENDING__;
const actionRecords=__ACTION_RECORDS__;
const previews=__PREVIEWS__;
const actions=actionRecords.map(a=>a.label);
const technology=system.ship?.technology_core;
let discussion=pending?.discussion?[...pending.discussion]:[];
function esc(value){return String(value).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]))}
function fillSelect(id){const el=document.getElementById(id);actionRecords.forEach((a,i)=>{const o=document.createElement('option');o.value=a.label;o.dataset.actionId=a.action_id;o.textContent=`${i+1}. ${a.label}`;el.appendChild(o)})}
fillSelect('humanAction');fillSelect('aiAction');
const active=state.command?.active_mode||system.active_command_mode;
document.getElementById('modes').innerHTML=Object.entries(modes).sort((a,b)=>a[1].number-b[1].number).map(([id,m])=>`<article class="mode ${id===active?'active':''}"><div class="number">0${m.number}</div><h2>${esc(m.title)}</h2><span class="badge">${esc(m.authority)}</span><p class="note">${esc(m.description)}</p></article>`).join('');
if(technology){const core=technology.selected_core;const known=(technology.known_parameter_summary||[]).slice(0,10).map(e=>`<div class="vote"><strong>${esc(e.id.replaceAll('_',' '))}</strong><div>${esc(e.value)} ${esc(e.unit||'')}</div><div class="note">${esc(e.truth_type)} · ${esc((e.source_ids||[]).join(', '))}</div></div>`).join('');const unsupported=(technology.blocked_calculations||[]).slice(0,6).map(x=>`<li>${esc(x.quantity)}: ${esc(x.reason)}</li>`).join('');document.getElementById('technology').innerHTML=`<p><span class="badge">${esc(technology.selected_core_id)}</span></p><h3>${esc(core.name)}</h3><p class="note">${esc(core.status.value)}</p>${known}<p class="note">Seed selected one equal catalog slot; no technology weighting or manual performance tuning was used.</p><ul class="note">${unsupported}</ul>`}else{document.getElementById('technology').textContent='No technology core profile found.'}
document.getElementById('recommendation').innerHTML=`<p><span class="badge">crew recommendation</span></p><strong>${esc(assessment.recommended_action)}</strong><p class="note">${esc(assessment.determinism_contract)}</p>`;
document.getElementById('actions').innerHTML=assessment.actions.map(row=>`<div class="action"><strong>${esc(row.action)}</strong><div class="note">${row.vote_count} crew votes · utility ${row.crew_average.toFixed(3)} · risk ${row.vector.effective_risk.toFixed(3)} · source ${esc(row.source_thread||'unknown')}</div><div class="bar"><span style="width:${Math.max(2,row.crew_average*100)}%"></span></div></div>`).join('');
function selectedRecord(){const label=document.getElementById('humanAction').value;return actionRecords.find(a=>a.label===label)||actionRecords[0]}
function renderPhysics(){const rec=selectedRecord();const p=previews[rec.action_id]?.physics_expectation;if(!p){document.getElementById('physics').textContent='No preview available.';return}document.getElementById('physics').innerHTML=`<div class="vote"><strong>${esc(rec.label)}</strong><div class="note">${esc(rec.intent)} · thread ${esc(rec.source_thread)}</div></div><div class="vote">Target <strong>${esc(p.target_planet_name)}</strong></div><div class="vote">Orbital phase <strong>${p.orbital_state.true_anomaly_deg.toFixed(2)}°</strong> · distance <strong>${p.orbital_state.star_distance_au.toFixed(4)} AU</strong></div><div class="vote">Expected SNR <strong>${p.sensor.expected_snr.toFixed(2)}</strong> · thermal ratio <strong>${p.thermal.thermal_load_ratio.toFixed(3)}</strong></div><div class="vote">Radiation risk <strong>${p.radiation.shielded_risk_index.toFixed(3)}</strong> · one-way delay <strong>${p.communications.one_way_light_time_s.toFixed(1)} s</strong></div><div class="vote">Reference transfer <strong>${p.trajectory.transfer_time_days.toFixed(2)} days</strong> · Δv <strong>${p.trajectory.total_delta_v_km_s.toFixed(3)} km/s</strong></div><p class="note">Expectation is fixed before the outcome entropy is sampled.</p>`}
document.getElementById('votes').innerHTML=assessment.votes.map(v=>`<div class="vote"><strong>${esc(v.seat_name)}</strong><div>${esc(v.action)}</div><div class="note">score ${v.score.toFixed(3)}</div></div>`).join('');
function renderDiscussion(){document.getElementById('discussion').innerHTML=discussion.length?discussion.map(m=>`<div class="message"><strong>${esc(m.speaker||'unknown')}</strong>${m.proposed_action?` <span class="badge">${esc(m.proposed_action)}</span>`:''}<div>${esc(m.message)}</div></div>`).join(''):'No discussion messages yet.'}
function compare(){const h=document.getElementById('humanAction').value,a=document.getElementById('aiAction').value,status=document.getElementById('status');if(h===a){status.innerHTML=`<strong class="good">Consensus reached.</strong><br>${esc(h)} can be submitted as matching final votes.`}else{status.innerHTML=`<strong class="warning">Discussion required.</strong><br>Human: ${esc(h)}<br>AI: ${esc(a)}<br>No automatic tie-break will execute either action.`}}
document.getElementById('compare').addEventListener('click',compare);document.getElementById('humanAction').addEventListener('change',renderPhysics);
document.getElementById('addMessage').addEventListener('click',()=>{const message=document.getElementById('message').value.trim();if(!message)return;const speaker=document.getElementById('speaker').value;const proposed_action=document.getElementById(speaker==='human'?'humanAction':'aiAction').value;discussion.push({speaker,message,proposed_action,created_at:new Date().toISOString()});document.getElementById('message').value='';renderDiscussion()});
document.getElementById('export').addEventListener('click',()=>{const packet={schema:'axm.browser-command-council-packet.v1',system_id:system.system_id,turn:state.turn+1,active_mode:active,human:{action:document.getElementById('humanAction').value,rationale:document.getElementById('humanWhy').value},ai:{action:document.getElementById('aiAction').value,rationale:document.getElementById('aiWhy').value},crew_assessment:assessment,discussion,exported_at:new Date().toISOString()};const blob=new Blob([JSON.stringify(packet,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`AXM_${system.system_id}_command_council.json`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)});
document.getElementById('timeline').innerHTML=ledger.length?ledger.map(e=>`<div class="event"><span class="badge">${esc(e.command?.mode||'unclassified')}</span> <strong>Turn ${e.turn} · ${esc(e.outcome.title)}</strong><div class="note">${esc(e.action)} · authority ${esc(e.command?.authority||'unknown')}</div></div>`).join(''):'<div class="note">No resolved commands yet.</div>';
if(pending){document.getElementById('humanAction').value=pending.proposals.human.action;document.getElementById('aiAction').value=pending.proposals.ai.action;document.getElementById('humanWhy').value=pending.proposals.human.rationale||'';document.getElementById('aiWhy').value=pending.proposals.ai.rationale||''}compare();renderDiscussion();renderPhysics();
</script></main></body></html>'''
    for marker, value in payloads.items():
        page = page.replace(marker, value)
    return page
