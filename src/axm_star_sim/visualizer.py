from __future__ import annotations

import html
import json
from typing import Any


def render_html(data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    title = html.escape(data["name"])
    template = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ — AXM Factual Star Adventure Simulator</title>
<style>
:root {
  color-scheme: dark;
  --bg:#05080c; --panel:#09121a; --panel2:#0d1822; --line:#2d4658;
  --text:#eaf4fa; --muted:#91a9b8; --accent:#70d7e8; --warm:#f2c879;
  --fact:#7dd3fc; --derived:#86efac; --prior:#fbbf24; --hyp:#c4b5fd; --spec:#f0abfc;
}
* { box-sizing:border-box; }
body { margin:0; background:radial-gradient(circle at 50% 0%,#0b1721 0,#05080c 50%); color:var(--text); font-family:Inter,Segoe UI,Arial,sans-serif; }
.shell { max-width:1500px; margin:auto; padding:14px; }
.topbar { display:flex; justify-content:space-between; gap:14px; align-items:flex-end; border-bottom:1px solid var(--line); padding:10px 4px 14px; }
h1 { margin:0; font-size:clamp(1.25rem,3vw,2.4rem); letter-spacing:.11em; font-weight:500; }
.kicker { color:var(--warm); text-transform:uppercase; letter-spacing:.28em; font-size:.72rem; }
.seed { color:var(--muted); font-family:ui-monospace,SFMono-Regular,Consolas,monospace; text-align:right; overflow-wrap:anywhere; }
.bridge { display:grid; grid-template-columns:minmax(190px,.75fr) minmax(0,3fr) minmax(220px,1fr); gap:10px; margin-top:10px; }
.panel { background:linear-gradient(180deg,rgba(13,24,34,.96),rgba(6,13,19,.96)); border:1px solid var(--line); border-radius:12px; padding:12px; }
.panel h2 { margin:0 0 10px; font-size:.78rem; font-weight:600; letter-spacing:.16em; color:var(--accent); text-transform:uppercase; }
.main-screen { min-height:650px; position:relative; overflow:hidden; padding:0; }
.main-screen:before { content:""; position:absolute; inset:0; pointer-events:none; background:linear-gradient(rgba(112,215,232,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(112,215,232,.035) 1px,transparent 1px); background-size:32px 32px; }
#systemSvg { width:100%; height:650px; display:block; }
.orbit { fill:none; stroke:#456276; stroke-width:1; opacity:.75; }
.orbit.temperate { stroke:var(--derived); stroke-dasharray:5 5; }
.planet { cursor:pointer; stroke:#eaf4fa; stroke-width:1; }
.planet:hover,.planet.active { stroke:var(--accent); stroke-width:3; }
.star { fill:url(#starGlow); }
.readout { display:grid; grid-template-columns:1fr auto; gap:6px 8px; font-size:.86rem; border-bottom:1px solid rgba(45,70,88,.5); padding:6px 0; }
.readout span:first-child { color:var(--muted); }
.readout strong { text-align:right; font-weight:500; }
.badge { display:inline-block; border:1px solid currentColor; border-radius:999px; padding:2px 7px; font-size:.66rem; text-transform:uppercase; letter-spacing:.06em; }
.catalog_fact { color:var(--fact); } .derived { color:var(--derived); } .simulation_prior { color:var(--prior); } .hypothesis { color:var(--hyp); } .speculation { color:var(--spec); }
.legend { display:flex; gap:6px; flex-wrap:wrap; margin-top:8px; }
.seed-tree { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:.72rem; color:var(--muted); max-height:270px; overflow:auto; }
.seed-row { display:grid; grid-template-columns:1fr auto; gap:5px; border-bottom:1px solid rgba(45,70,88,.35); padding:4px 0; }
.opportunity { border-left:3px solid var(--warm); padding-left:10px; }
.opportunity h3 { margin:0 0 8px; font-size:1.08rem; }
ul { padding-left:20px; } li { margin:5px 0; color:#cbd9e2; }
.bottom { display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; margin-top:10px; }
.small { font-size:.76rem; color:var(--muted); }
button { background:#0d2230; color:var(--text); border:1px solid var(--line); border-radius:8px; padding:8px 10px; cursor:pointer; }
button:hover { border-color:var(--accent); }
.truth-note { color:var(--muted); font-size:.78rem; line-height:1.45; }
@media (max-width:950px) { .bridge { grid-template-columns:1fr; } .main-screen { order:-1; min-height:500px; } #systemSvg { height:500px; } .bottom { grid-template-columns:1fr; } .seed { text-align:left; } .topbar { align-items:flex-start; flex-direction:column; } }
</style>
</head>
<body>
<div class="shell">
  <header class="topbar">
    <div><div class="kicker">AXM factual star adventure simulator · v0.6.0</div><h1>__TITLE__</h1></div>
    <div class="seed">SYSTEM <span id="systemId"></span><br>SEED <span id="masterSeed"></span></div>
  </header>

  <main class="bridge">
    <aside class="panel">
      <h2>Stellar analysis</h2>
      <div id="starReadouts"></div>
      <h2 style="margin-top:18px">Truth layers</h2>
      <div class="legend">
        <span class="badge catalog_fact">catalog</span>
        <span class="badge derived">derived</span>
        <span class="badge simulation_prior">prior</span>
        <span class="badge hypothesis">hypothesis</span>
      </div>
      <p class="truth-note">A prior is generated input, not an observation. A derived value points to its formula. A hypothesis remains uncertain until the adventure creates an observation path.</p>
    </aside>

    <section class="panel main-screen">
      <svg id="systemSvg" viewBox="0 0 900 650" role="img" aria-label="Generated star system orbital visualization">
        <defs><radialGradient id="starGlow"><stop offset="0" stop-color="#fff8cf"/><stop offset=".45" stop-color="#ffd873"/><stop offset="1" stop-color="#e89134"/></radialGradient></defs>
        <g id="stars"></g><g id="orbits"></g><g id="bodies"></g>
      </svg>
    </section>

    <aside class="panel">
      <h2>Selected world</h2>
      <div id="planetTitle" style="font-size:1.35rem;margin-bottom:8px"></div>
      <div id="planetReadouts"></div>
      <h2 style="margin-top:18px">Adventure opportunity</h2>
      <div class="opportunity"><h3 id="oppTitle"></h3><div class="small" id="oppTone"></div><p id="oppTrigger" class="truth-note"></p></div>
    </aside>
  </main>

  <section class="bottom">
    <div class="panel"><h2>Possible observations</h2><ul id="observations"></ul></div>
    <div class="panel"><h2>Current hypotheses</h2><ul id="hypotheses"></ul></div>
    <div class="panel"><h2>Available actions</h2><ul id="actions"></ul></div>
    <div class="panel"><h2>Ship state</h2><div id="shipReadouts"></div></div>
    <div class="panel"><h2>Factual technology core</h2><div id="technologyCore"></div></div>
    <div class="panel"><h2>Party director</h2><div id="partyReadouts"></div></div>
    <div class="panel"><h2>Seed branches</h2><div id="seedTree" class="seed-tree"></div></div>
    <div class="panel"><h2>Open future contract</h2><div id="futureContract"></div><p class="truth-note">Continue in <strong>adventure_console.html</strong> or use the Python <strong>evolve</strong> command.</p></div>
  </section>
</div>
<script id="axmData" type="application/json">__PAYLOAD__</script>
<script>
const data = JSON.parse(document.getElementById('axmData').textContent);
const fmt = (v) => typeof v === 'number' ? new Intl.NumberFormat(undefined,{maximumFractionDigits:4}).format(v) : String(v);
const unit = (u) => u ? ' ' + u.replaceAll('_',' ') : '';
const evidenceRow = (label,e) => `<div class="readout"><span>${label}</span><strong>${fmt(e.value)}${unit(e.unit)}<br><span class="badge ${e.truth_type}">${e.truth_type.replace('_',' ')}</span></strong></div>`;

document.getElementById('systemId').textContent = data.system_id;
document.getElementById('masterSeed').textContent = data.master_seed;
const starFields = [['profile','Profile'],['mass','Mass'],['radius','Radius'],['effective_temperature','Temperature'],['luminosity','Luminosity'],['age','Age'],['metallicity','Metallicity']];
document.getElementById('starReadouts').innerHTML = starFields.map(([k,l])=>evidenceRow(l,data.star[k])).join('');

const svg = document.getElementById('systemSvg');
const starsLayer = document.getElementById('stars');
for(let i=0;i<180;i++){
  const c=document.createElementNS('http://www.w3.org/2000/svg','circle');
  const h = [...data.seed_manifest.presentation].reduce((a,ch)=>((a*31+ch.charCodeAt(0)+i)%100000),i+1);
  c.setAttribute('cx',(h*37)%900); c.setAttribute('cy',(h*61)%650); c.setAttribute('r',.35+(h%15)/20); c.setAttribute('fill','#b9d6e5'); c.setAttribute('opacity',.18+(h%70)/100); starsLayer.appendChild(c);
}
const center={x:450,y:325};
const maxAxis=Math.max(...data.planets.map(p=>p.facts.semi_major_axis.value));
const scale=285/Math.sqrt(maxAxis);
const orbits=document.getElementById('orbits'); const bodies=document.getElementById('bodies');
const star=document.createElementNS('http://www.w3.org/2000/svg','circle');
star.setAttribute('cx',center.x);star.setAttribute('cy',center.y);star.setAttribute('r',22);star.setAttribute('class','star');bodies.appendChild(star);

function selectPlanet(index){
  document.querySelectorAll('.planet').forEach((n,i)=>n.classList.toggle('active',i===index));
  const p=data.planets[index]; document.getElementById('planetTitle').textContent=`${data.name} ${p.name} · ${p.kind}`;
  const fields=[['semi_major_axis','Orbit'],['orbital_period','Year'],['radius','Radius'],['mass','Mass'],['density','Density'],['surface_gravity','Gravity'],['equilibrium_temperature','Eq. temperature'],['insolation','Stellar flux'],['eccentricity','Eccentricity'],['temperate_screen','Temperate screen']];
  document.getElementById('planetReadouts').innerHTML=fields.map(([k,l])=>evidenceRow(l,p.facts[k])).join('');
}

data.planets.forEach((p,index)=>{
  const axis=Math.sqrt(p.facts.semi_major_axis.value)*scale;
  const ry=axis*.42;
  const orbit=document.createElementNS('http://www.w3.org/2000/svg','ellipse');
  orbit.setAttribute('cx',center.x); orbit.setAttribute('cy',center.y); orbit.setAttribute('rx',axis); orbit.setAttribute('ry',ry);
  orbit.setAttribute('class','orbit'+(p.facts.temperate_screen.value?' temperate':'')); orbits.appendChild(orbit);
  const angle=p.visual.phase_deg*Math.PI/180; const x=center.x+axis*Math.cos(angle), y=center.y+ry*Math.sin(angle);
  const body=document.createElementNS('http://www.w3.org/2000/svg','circle');
  body.setAttribute('cx',x);body.setAttribute('cy',y);body.setAttribute('r',p.visual.size_hint);body.setAttribute('class','planet');body.setAttribute('data-index',index);
  const fill={"terrestrial":"#9fb0b6","super-earth":"#c58b64","neptune-like":"#5da9c8","gas-giant":"#d5b27a"}[p.kind]||'#aaa'; body.setAttribute('fill',fill);
  body.addEventListener('click',()=>selectPlanet(index)); bodies.appendChild(body);
  const label=document.createElementNS('http://www.w3.org/2000/svg','text'); label.setAttribute('x',x+12);label.setAttribute('y',y-10);label.setAttribute('fill','#dcecf5');label.setAttribute('font-size','12');label.textContent=p.name;bodies.appendChild(label);
});
selectPlanet(0);

const opp=data.adventure.selected_opportunity;
document.getElementById('oppTitle').textContent=opp.title;
document.getElementById('oppTone').textContent=`Direction: ${data.party_director.dominant_direction} · opportunity tone: ${opp.tone}`;
document.getElementById('oppTrigger').textContent='Triggered by: '+Object.entries(opp.trigger).map(([k,v])=>`${k}=${v}`).join(' · ');
const fillList=(id,items)=>document.getElementById(id).innerHTML=items.map(x=>`<li>${x}</li>`).join('');
fillList('observations',opp.observations);fillList('hypotheses',opp.hypotheses);fillList('actions',opp.actions);

document.getElementById('shipReadouts').innerHTML=evidenceRow('Ship',{value:data.ship.name,unit:null,truth_type:'simulation_prior'})+evidenceRow('Role',{value:data.ship.role,unit:null,truth_type:'simulation_prior'})+Object.entries(data.ship.systems).map(([k,v])=>evidenceRow(k.replaceAll('_',' '),{value:v,unit:k.includes('percent')?'%':null,truth_type:'simulation_prior'})).join('');
const tech=data.ship.technology_core;const core=tech.selected_core;
const known=(tech.known_parameter_summary||[]).slice(0,8).map(e=>evidenceRow(e.id.replaceAll('_',' '),e)).join('');
const supported=(tech.exploration_function_translation||[]).filter(x=>x.supported_by_selected_core).map(x=>`<li><strong>${x.function_id.replaceAll('_',' ')}</strong>: ${x.real_translation}</li>`).join('');
document.getElementById('technologyCore').innerHTML=`<div class="readout"><span>Reference lineage</span><strong>${core.name}<br><span class="badge catalog_fact">catalog grounded</span></strong></div><div class="readout"><span>Status</span><strong>${core.status.value}</strong></div><div class="readout"><span>Selection</span><strong>seeded equal catalog slot ${tech.selection_receipt.selected_index+1}/${tech.selection_receipt.eligible_count}</strong></div>${known}<p class="truth-note">Unknown performance remains unknown. This is a source-pinned lineage, not a claim that the AXM ship is an exact copy.</p>${supported?`<ul>${supported}</ul>`:''}`;
document.getElementById('partyReadouts').innerHTML=Object.entries(data.party_director.weights).map(([k,v])=>`<div class="readout"><span>${k}</span><strong>${v} weight</strong></div>`).join('')+`<p class="truth-note">${data.party_director.rule}</p>`;
document.getElementById('seedTree').innerHTML=Object.entries(data.seed_manifest).map(([k,v])=>`<div class="seed-row"><span>${k}</span><span>${v.slice(0,12)}</span></div>`).join('');
const fc=data.adventure.future_contract||{};document.getElementById('futureContract').innerHTML=Object.entries(fc).map(([k,v])=>`<div class="readout"><span>${k.replaceAll('_',' ')}</span><strong>${Array.isArray(v)?v.join(', '):String(v)}</strong></div>`).join('');
</script>
</body>
</html>'''
    return template.replace('__TITLE__', title).replace('__PAYLOAD__', payload)
