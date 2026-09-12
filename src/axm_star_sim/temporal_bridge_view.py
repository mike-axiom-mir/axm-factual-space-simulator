from __future__ import annotations

import html
import json
from typing import Any


_TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="color-scheme" content="dark">
<title>__AXM_TITLE__ — AXM Temporal Evidence Bridge v0.14</title>
<style>
:root{--ink:#edfaff;--muted:#8ea9b8;--bg:#010407;--panel:#07131b;--panel2:#0b1c27;--line:#274a5b;--cyan:#63e8ff;--mint:#82f3c2;--amber:#ffd078;--violet:#b9a5ff;--rose:#ff91a0;--shadow:0 22px 75px rgba(0,0,0,.46)}
*{box-sizing:border-box} html,body{margin:0;min-height:100%;background:radial-gradient(circle at 48% -10%,#17384e 0,#06121a 34%,var(--bg) 72%);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
body{padding:clamp(8px,1.5vw,20px)} button,select,input{font:inherit} .shell{max-width:1720px;margin:auto}
.top{display:flex;gap:18px;align-items:flex-end;justify-content:space-between;padding:8px 4px 16px;border-bottom:1px solid rgba(99,232,255,.24)}
.eyebrow{color:var(--amber);font-size:.7rem;letter-spacing:.24em;text-transform:uppercase}.top h1{margin:.28rem 0 0;font-weight:540;font-size:clamp(1.4rem,3vw,2.7rem);letter-spacing:.055em}.subtitle{color:var(--muted);max-width:800px;line-height:1.48;margin:.55rem 0 0}
.pills{display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-end}.pill{border:1px solid currentColor;border-radius:999px;padding:5px 9px;font-size:.66rem;letter-spacing:.08em;text-transform:uppercase}.ok{color:var(--mint)}.hold{color:var(--amber)}.info{color:var(--cyan)}
.bridge{display:grid;grid-template-columns:minmax(230px,.82fr) minmax(500px,2.55fr) minmax(270px,1fr);gap:10px;margin-top:10px}.panel{background:linear-gradient(180deg,rgba(12,30,41,.95),rgba(4,12,18,.97));border:1px solid var(--line);border-radius:15px;box-shadow:var(--shadow);overflow:hidden}.panelPad{padding:14px}.sideScroll{height:720px;overflow:auto;scrollbar-color:#31566a transparent}
.panel h2{margin:0 0 10px;color:var(--cyan);font-size:.72rem;letter-spacing:.18em;text-transform:uppercase;font-weight:700}.fine{font-size:.73rem;color:var(--muted);line-height:1.5}.mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere}
.canvasWrap{position:relative;min-height:720px;background:#02070b;overflow:hidden}#bridgeCanvas{display:block;width:100%;height:720px;touch-action:none}
.canvasTop{position:absolute;left:12px;right:12px;top:12px;display:flex;align-items:flex-start;justify-content:space-between;gap:10px;pointer-events:none}.canvasBadge,.clockCard{background:rgba(2,8,13,.82);border:1px solid rgba(99,232,255,.3);backdrop-filter:blur(9px);border-radius:11px;padding:8px 10px;font-size:.71rem;line-height:1.45}.canvasBadge{max-width:54%}.phase{color:var(--amber);font-weight:780;letter-spacing:.12em;text-transform:uppercase}.clockDeck{display:grid;grid-template-columns:auto auto;gap:6px}.clockCard{min-width:124px;text-align:right}.clockCard span{display:block;color:var(--muted);font-size:.55rem;letter-spacing:.11em;text-transform:uppercase}.clockCard b{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.76rem;font-weight:650}.clockCard.source{border-color:rgba(130,243,194,.42)}.clockCard.source b{color:var(--mint)}
.truthBar{position:absolute;left:12px;right:12px;bottom:12px;display:flex;gap:7px;flex-wrap:wrap;pointer-events:none}.truthChip{background:rgba(2,8,13,.84);border:1px solid var(--line);border-radius:999px;padding:5px 8px;font-size:.63rem;color:var(--muted)}
.controlGrid{display:grid;gap:8px}.buttonRow{display:grid;grid-template-columns:1fr 1fr;gap:7px}label{display:grid;gap:5px;color:var(--muted);font-size:.71rem}select,button{color:var(--ink);background:#0a2230;border:1px solid #31586c;border-radius:9px;padding:9px 10px}input[type=range]{width:100%;accent-color:var(--amber)}button{cursor:pointer}button:hover,button:focus-visible,select:focus-visible,input:focus-visible{border-color:var(--cyan);outline:2px solid rgba(99,232,255,.17);outline-offset:2px}button.primary{background:linear-gradient(120deg,#12394b,#115044);border-color:#41ae99}button.secondary{background:#0a1721}.check{display:flex;gap:8px;align-items:center;padding:5px 0}.check input{width:17px;height:17px;accent-color:var(--mint)}.keyHint{border:1px solid rgba(39,74,91,.55);border-radius:9px;padding:8px;margin-top:8px}
.receipt{border-left:3px solid var(--mint);padding-left:10px;margin:12px 0}.receipt strong{color:var(--mint)}.metric{display:grid;grid-template-columns:1fr auto;gap:5px 9px;padding:6px 0;border-bottom:1px solid rgba(39,74,91,.52);font-size:.75rem}.metric span{color:var(--muted)}.metric b{font-weight:580;text-align:right}.sectionRule{border:0;border-top:1px solid rgba(39,74,91,.5);margin:14px 0}
.eventTitle{font-size:1.02rem;line-height:1.38;margin:0 0 9px}.eventText{font-size:.77rem;line-height:1.5;color:#c9dde7}.truthType,.stateTag{display:inline-block;border:1px solid currentColor;border-radius:999px;padding:2px 6px;font-size:.59rem;text-transform:uppercase;letter-spacing:.07em}.truthType{color:var(--violet)}.stateTag.history{color:var(--violet)}.stateTag.head{color:var(--mint)}.stateTag.unknown{color:var(--amber)}.stateTag.inspect{color:var(--cyan)}
.deltaGrid{display:grid;gap:9px}.deltaRow{display:grid;gap:5px}.deltaMeta{display:grid;grid-template-columns:1fr auto;gap:8px;font-size:.69rem}.deltaMeta span{color:var(--muted)}.deltaMeta b{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-weight:650}.deltaTrack{height:6px;border-radius:999px;background:#102733;overflow:hidden}.deltaFill{height:100%;min-width:2px;border-radius:999px}.deltaFill.increase{background:var(--cyan)}.deltaFill.decrease{background:var(--violet)}.deltaFill.no_change{background:var(--muted)}
.timeline{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.timeline button{text-align:left;min-height:112px;padding:9px;background:rgba(7,19,27,.94);position:relative;overflow:hidden}.timeline button::before{content:"";position:absolute;left:0;right:0;top:0;height:3px;background:var(--violet);opacity:.45}.timeline button.head::before{background:var(--mint);opacity:.9}.timeline button.active{border-color:var(--amber);box-shadow:inset 0 0 0 1px rgba(255,208,120,.32)}.timeline small{display:block;color:var(--muted);margin-top:5px;line-height:1.35}.timeline .timeRange{color:var(--cyan);font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.67rem}.timeline .timelineState{margin-top:7px;color:var(--muted);font-size:.59rem;letter-spacing:.08em;text-transform:uppercase}
.bottom{display:grid;grid-template-columns:1.1fr 1fr 1fr;gap:10px;margin-top:10px}.resources{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.resource,.legendCard{border:1px solid rgba(39,74,91,.72);border-radius:11px;padding:9px;background:rgba(5,17,24,.72)}.resource b{display:block;color:var(--mint);font-size:.98rem}.resource span,.legendCard span{font-size:.66rem;color:var(--muted)}.legendGrid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.legendCard b{display:block;font-size:.7rem;color:var(--cyan);margin-bottom:3px}.boundary{border-left:3px solid var(--amber);padding-left:10px;color:#d7e6ed;font-size:.75rem;line-height:1.52}.srOnly{position:absolute!important;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
@media(max-width:1120px){.bridge{grid-template-columns:1fr 1fr}.canvasPanel{grid-column:1/-1;grid-row:1}.sideScroll{height:auto;max-height:none}.canvasWrap,#bridgeCanvas{min-height:590px;height:590px}.bottom{grid-template-columns:1fr 1fr}.bottom .panel:first-child{grid-column:1/-1}}
@media(max-width:720px){body{padding:6px}.top{align-items:flex-start;flex-direction:column}.pills{justify-content:flex-start}.bridge,.bottom{grid-template-columns:1fr}.bottom .panel:first-child{grid-column:auto}.canvasWrap,#bridgeCanvas{min-height:510px;height:510px}.timeline{grid-template-columns:1fr 1fr}.resources{grid-template-columns:1fr 1fr}.canvasBadge{max-width:72%}.clockDeck{grid-template-columns:1fr}.clockCard{min-width:106px;padding:6px 8px}.clockCard b{font-size:.67rem}.truthBar{right:8px;left:8px;bottom:8px}.truthChip:nth-child(n+3){display:none}}
@media(max-width:430px){.timeline{grid-template-columns:1fr}.canvasBadge{max-width:64%;font-size:.64rem}.clockCard{min-width:94px}.legendGrid{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
</style>
</head>
<body>
<div class="shell">
  <header class="top">
    <div><div class="eyebrow">AXM factual simulator · temporal evidence bridge v0.14</div><h1>__AXM_TITLE__</h1><p class="subtitle">A verified v0.15 event history moving through a replaceable renderer. Scrub causal receipts, inspect any known object, and see recorded state changes without granting the presentation authority over source truth.</p></div>
    <div class="pills"><span class="pill ok">fixture verified</span><span class="pill info">inspect-only cameras</span><span class="pill hold">GitHub merge held</span></div>
  </header>
  <main class="bridge">
    <aside class="panel"><div class="panelPad sideScroll">
      <h2>Playback controls</h2>
      <div class="controlGrid">
        <button id="playToggle" class="primary" type="button" aria-pressed="false">Start causal playback</button>
        <div class="buttonRow"><button id="previousCue" class="secondary" type="button">Previous receipt</button><button id="nextCue" class="secondary" type="button">Next receipt</button></div>
        <button id="resetButton" class="secondary" type="button">Reset to first receipt</button>
        <label>Replay scrubber<input id="replayScrubber" type="range" min="0" value="0" step="0.01" aria-describedby="scrubLabel"><span id="scrubLabel" class="fine mono">00:00.0 · receipt 1</span></label>
        <label>Playback speed<select id="speedSelect"><option value="0.5">0.5× calm</option><option value="1" selected>1×</option><option value="2">2×</option><option value="4">4×</option></select></label>
        <label>Receipt focus<select id="cueSelect"></select></label>
        <label>Camera framing<select id="cameraSelect"></select></label>
        <label>Inspect object<select id="inspectSelect"></select></label>
        <label>Label density<select id="labelSelect"><option value="focus" selected>Focus labels</option><option value="all">All planet labels</option><option value="minimal">Minimal labels</option></select></label>
        <label class="check"><input id="autoAdvance" type="checkbox" checked> Continue across receipts</label>
        <label class="check"><input id="reducedMotion" type="checkbox"> Reduced motion / stay paused</label>
      </div>
      <div id="statusLine" class="receipt" aria-live="polite"><strong>PAUSED</strong><p class="fine">Ready at the first immutable receipt.</p></div>
      <div class="keyHint fine">Keyboard on canvas: Space play/pause · ←/→ receipt · C camera · I inspector.</div>
      <hr class="sectionRule"><h2>Source gate</h2><div id="sourcePanel"></div>
    </div></aside>
    <section class="panel canvasPanel">
      <div class="canvasWrap">
        <canvas id="bridgeCanvas" tabindex="0" role="img" aria-label="Animated factual star-system renderer with separate source mission and replay display clocks"></canvas>
        <div class="canvasTop">
          <div class="canvasBadge"><span id="phaseLabel" class="phase">paused</span><div id="cueHeadline">Receipt playback ready</div><div class="fine" id="framingLabel">System overview · focus labels</div></div>
          <div class="clockDeck">
            <div class="clockCard source"><span>SOURCE MISSION</span><b id="missionClockLabel">T+UNKNOWN</b></div>
            <div class="clockCard"><span>REPLAY DISPLAY</span><b id="displayClockLabel">00:00.0</b></div>
          </div>
        </div>
        <div class="truthBar"><span class="truthChip">Orbit · compressed geometry</span><span class="truthChip">Signal · causal explanation</span><span class="truthChip">Replay · no mission authority</span><span class="truthChip">History · immutable input</span></div>
      </div>
    </section>
    <aside class="panel"><div class="panelPad sideScroll">
      <h2>Active event receipt</h2><div id="eventPanel"></div>
      <hr class="sectionRule"><h2>Temporal receipt</h2><div id="temporalPanel"></div>
      <hr class="sectionRule"><h2>Signal receipt</h2><div id="signalPanel"></div>
      <hr class="sectionRule"><h2>Recorded state changes</h2><div id="deltaPanel"></div>
      <hr class="sectionRule"><h2>Object inspector</h2><div id="targetPanel"></div>
    </div></aside>
  </main>
  <section class="panel" style="margin-top:10px"><div class="panelPad"><h2>Four-event mission-time passage</h2><div id="timeline" class="timeline"></div></div></section>
  <section class="bottom">
    <div class="panel"><div class="panelPad"><h2>Authoritative runtime snapshot — read only</h2><div id="resources" class="resources"></div></div></div>
    <div class="panel"><div class="panelPad"><h2>Time legend</h2><div class="legendGrid"><div class="legendCard"><b>Source mission</b><span>Copied from runtime state; renderer cannot advance it.</span></div><div class="legendCard"><b>Receipt range</b><span>Derived only when recorded durations reconcile to the source clock.</span></div><div class="legendCard"><b>Replay display</b><span>Local animation time; disposable and resettable.</span></div><div class="legendCard"><b>Wall-clock age</b><span>Unknown here; no verified observation timestamps were imported.</span></div></div></div></div>
    <div class="panel"><div class="panelPad"><h2>Authority boundary</h2><div class="boundary">The renderer may move pixels, scrub replay time, inspect-only cameras, labels, recorded delta bars, and compressed display phases. It may not retarget an event, alter runtime resources, advance mission time, append an event, deliver a command, accept evidence, alter a truth label, clear uncertainty, or prove route feasibility. Main-repository semantic verification and Mike's merge gate remain required.</div></div></div>
  </section>
</div>
<script id="axmStoryboard" type="application/json">__AXM_STORYBOARD__</script>
<script id="axmImportReceipt" type="application/json">__AXM_RECEIPT__</script>
<script>
'use strict';
const STORY=JSON.parse(document.getElementById('axmStoryboard').textContent);
const IMPORT=JSON.parse(document.getElementById('axmImportReceipt').textContent);
const $=id=>document.getElementById(id);const canvas=$('bridgeCanvas');const ctx=canvas.getContext('2d');
let playing=false,reduced=false,displaySeconds=0,frameCount=0,lastTime=null,rafId=null,selectedCue=0,cameraPreset=STORY.presentation_profiles.default_camera_preset,labelMode=STORY.presentation_profiles.default_label_mode,inspectPlanetId='';
const CUE_SECONDS=8,TOTAL_DISPLAY_SECONDS=STORY.cues.length*CUE_SECONDS,MAX_SCRUB_SECONDS=Math.max(0,TOTAL_DISPLAY_SECONDS-.001),TAU=Math.PI*2,clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
const esc=v=>String(v??'unknown').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const finite=v=>v!==null&&v!==''&&Number.isFinite(Number(v));
function speed(){return Math.max(.1,Number($('speedSelect').value||1))}
function formatMission(value){if(!finite(value))return'T+UNKNOWN';const n=Number(value),sign=n<0?'T−':'T+',minutes=Math.round(Math.abs(n)*60);return`${sign}${String(Math.floor(minutes/60)).padStart(2,'0')}:${String(minutes%60).padStart(2,'0')}`}
function formatDelta(value){if(!finite(value))return'UNKNOWN';const n=Number(value);if(Math.abs(n)<1e-9)return'AT CURRENT';const minutes=Math.round(Math.abs(n)*60),sign=n<0?'−':'+';return`${sign}${String(Math.floor(minutes/60)).padStart(2,'0')}:${String(minutes%60).padStart(2,'0')}`}
function sample(){const count=STORY.cues.length,cycle=displaySeconds/CUE_SECONDS;let index=$('autoAdvance').checked?Math.floor(cycle)%count:selectedCue;index=Math.max(0,Math.min(count-1,index));const phase=cycle-Math.floor(cycle);let segment,segmentPhase;if(phase<.30){segment='command_outbound';segmentPhase=phase/.30}else if(phase<.54){segment='observation_window';segmentPhase=(phase-.30)/.24}else{segment='telemetry_return';segmentPhase=(phase-.54)/.46}return{index,phase,segment,segmentPhase:clamp(segmentPhase),cue:STORY.cues[index]}}
function fit(){const dpr=Math.max(1,Math.min(2,window.devicePixelRatio||1)),rect=canvas.getBoundingClientRect();canvas.width=Math.max(1,Math.round(rect.width*dpr));canvas.height=Math.max(1,Math.round(rect.height*dpr));ctx.setTransform(dpr,0,0,dpr,0,0);draw()}
function seededStars(width,height){const stars=[];let seed=2166136261;for(const ch of STORY.system_id)seed=Math.imul(seed^ch.charCodeAt(0),16777619)>>>0;for(let i=0;i<190;i++){seed=(Math.imul(seed,1664525)+1013904223)>>>0;const x=(seed/4294967296)*width;seed=(Math.imul(seed,1664525)+1013904223)>>>0;const y=(seed/4294967296)*height;seed=(Math.imul(seed,1664525)+1013904223)>>>0;const size=.3+(seed/4294967296)*1.35;seed=(Math.imul(seed,1664525)+1013904223)>>>0;stars.push([x,y,size,(seed/4294967296)*TAU])}return stars}
function geometry(){const rect=canvas.getBoundingClientRect(),w=rect.width,h=rect.height,cx=w*.5,cy=h*.53,maxA=Math.max(...STORY.planets.map(p=>p.semi_major_axis_au),1),maxR=Math.min(w,h)*.39,logMax=Math.log1p(maxA*18),radius=a=>42+(maxR-42)*(Math.log1p(Math.max(0,a)*18)/logMax);return{w,h,cx,cy,maxR,radius}}
function planetPoint(planet,g){const days=displaySeconds*2.2,period=Math.max(.1,planet.orbital_period_days||1),angle=(planet.initial_display_phase_deg*Math.PI/180)+TAU*(days/period),r=g.radius(planet.semi_major_axis_au);return{x:g.cx+Math.cos(angle)*r,y:g.cy+Math.sin(angle)*r*.54,angle,r}}
function shipPoint(g){const r=g.radius(STORY.ship_orbit_au||0),angle=-.62+Math.sin(displaySeconds*.12)*.08;return{x:g.cx+Math.cos(angle)*r,y:g.cy+Math.sin(angle)*r*.54,angle,r}}
function cameraSpec(g,ship,target,inspected){if(cameraPreset==='target_focus')return{x:inspected.x,y:inspected.y,scale:g.w<600?1.55:2.05};if(cameraPreset==='signal_lane')return{x:(ship.x+target.x)/2,y:(ship.y+target.y)/2,scale:g.w<600?1.22:1.48};return{x:g.cx,y:g.cy,scale:1}}
function glow(x,y,rgb,size,alpha=1){const gr=ctx.createRadialGradient(x,y,0,x,y,size);gr.addColorStop(0,`rgba(${rgb},${alpha})`);gr.addColorStop(.28,`rgba(${rgb},${alpha*.42})`);gr.addColorStop(1,`rgba(${rgb},0)`);ctx.fillStyle=gr;ctx.beginPath();ctx.arc(x,y,size,0,TAU);ctx.fill()}
function pulse(from,to,phase,rgb,label,scale){const p=clamp(phase),x=from.x+(to.x-from.x)*p,y=from.y+(to.y-from.y)*p;ctx.save();ctx.strokeStyle=`rgba(${rgb},.3)`;ctx.setLineDash([5/scale,7/scale]);ctx.lineWidth=1.2/scale;ctx.beginPath();ctx.moveTo(from.x,from.y);ctx.lineTo(to.x,to.y);ctx.stroke();ctx.setLineDash([]);glow(x,y,rgb,18/scale+5*Math.sin(p*TAU*3)**2);ctx.fillStyle=`rgb(${rgb})`;ctx.font=`${11/scale}px system-ui`;ctx.fillText(label,x+10/scale,y-8/scale);ctx.restore()}
function draw(){const g=geometry(),s=sample(),points={};ctx.clearRect(0,0,g.w,g.h);const bg=ctx.createLinearGradient(0,0,0,g.h);bg.addColorStop(0,'#071823');bg.addColorStop(.58,'#02090e');bg.addColorStop(1,'#010305');ctx.fillStyle=bg;ctx.fillRect(0,0,g.w,g.h);const nebula=ctx.createRadialGradient(g.w*.58,g.h*.44,0,g.w*.58,g.h*.44,g.maxR*1.8);nebula.addColorStop(0,'rgba(31,91,117,.18)');nebula.addColorStop(.45,'rgba(78,48,112,.07)');nebula.addColorStop(1,'rgba(0,0,0,0)');ctx.fillStyle=nebula;ctx.fillRect(0,0,g.w,g.h);for(const star of seededStars(g.w,g.h)){const twinkle=reduced?0:Math.sin(displaySeconds*.8+star[3])*.08;ctx.globalAlpha=.2+star[2]*.27+twinkle;ctx.fillStyle='#d9f2ff';ctx.fillRect(star[0],star[1],star[2],star[2])}ctx.globalAlpha=1;
  for(const p of STORY.planets)points[p.planet_id]=planetPoint(p,g);const ship=shipPoint(g),target=points[s.cue.target_planet_id]||{x:g.cx,y:g.cy},inspectedId=inspectPlanetId||s.cue.target_planet_id,inspected=points[inspectedId]||target,cam=cameraSpec(g,ship,target,inspected);ctx.save();ctx.translate(g.cx,g.cy);ctx.scale(cam.scale,cam.scale);ctx.translate(-cam.x,-cam.y);
  for(const p of STORY.planets){const q=points[p.planet_id],active=p.planet_id===s.cue.target_planet_id;ctx.strokeStyle=active?'rgba(255,208,120,.58)':'rgba(75,124,149,.33)';ctx.lineWidth=(active?1.35:1)/cam.scale;ctx.beginPath();ctx.ellipse(g.cx,g.cy,q.r,q.r*.54,0,0,TAU);ctx.stroke()}
  glow(g.cx,g.cy,'255,213,119',46/cam.scale);ctx.fillStyle='#fff0b4';ctx.beginPath();ctx.arc(g.cx,g.cy,8/cam.scale,0,TAU);ctx.fill();
  for(const p of STORY.planets){const q=points[p.planet_id],active=p.planet_id===s.cue.target_planet_id,inspectedOnly=p.planet_id===inspectedId&&!active,size=Math.max(3,Math.min(8,p.size_hint*.82))/Math.sqrt(cam.scale);if(active)glow(q.x,q.y,'99,232,255',(22+5*Math.sin(displaySeconds*3)**2)/cam.scale);if(inspectedOnly){ctx.strokeStyle='rgba(185,165,255,.92)';ctx.lineWidth=1.5/cam.scale;ctx.beginPath();ctx.arc(q.x,q.y,size+6/cam.scale,0,TAU);ctx.stroke()}ctx.fillStyle=active?'#9cf4ff':(p.kind==='gas_giant'||p.kind==='neptune-like'?'#d8ae7c':'#a6c1d0');ctx.beginPath();ctx.arc(q.x,q.y,size,0,TAU);ctx.fill();const show=labelMode==='all'||active||inspectedOnly;if(show){ctx.fillStyle=active?'#d1fbff':(inspectedOnly?'#d6ccff':'#8faab8');ctx.font=active||inspectedOnly?`600 ${12/cam.scale}px system-ui`:`${10/cam.scale}px system-ui`;ctx.fillText(p.name,q.x+9/cam.scale,q.y-7/cam.scale)}}
  ctx.save();ctx.translate(ship.x,ship.y);ctx.rotate(ship.angle+Math.PI/2);ctx.fillStyle='#82f3c2';ctx.beginPath();ctx.moveTo(0,-9/cam.scale);ctx.lineTo(6/cam.scale,7/cam.scale);ctx.lineTo(0,4/cam.scale);ctx.lineTo(-6/cam.scale,7/cam.scale);ctx.closePath();ctx.fill();ctx.restore();if(labelMode!=='minimal'){ctx.fillStyle='#82f3c2';ctx.font=`${10/cam.scale}px system-ui`;ctx.fillText('observer',ship.x+9/cam.scale,ship.y+14/cam.scale)}
  if(s.segment==='command_outbound')pulse(ship,target,s.segmentPhase,'255,208,120','command',cam.scale);else if(s.segment==='observation_window'){ctx.strokeStyle='rgba(185,165,255,.92)';ctx.lineWidth=2/cam.scale;ctx.beginPath();ctx.arc(target.x,target.y,(15+10*s.segmentPhase)/cam.scale,0,TAU);ctx.stroke();ctx.fillStyle='#cdbfff';ctx.font=`${11/cam.scale}px system-ui`;ctx.fillText('observation window',target.x+15/cam.scale,target.y+18/cam.scale)}else pulse(target,ship,s.segmentPhase,'130,243,194','telemetry',cam.scale);ctx.restore();
  const vignette=ctx.createRadialGradient(g.cx,g.cy,g.maxR*.4,g.cx,g.cy,Math.max(g.w,g.h)*.7);vignette.addColorStop(0,'rgba(0,0,0,0)');vignette.addColorStop(1,'rgba(0,0,0,.48)');ctx.fillStyle=vignette;ctx.fillRect(0,0,g.w,g.h);updatePanels(s);const tr=s.cue.temporal_receipt||{},changes=s.cue.state_change_receipt?.changes||[];window.__axmMainBridge={schema:'axm.main-simulator-renderer-runtime.v1',version:'0.14.0',playing,frameCount,displaySeconds:Number(displaySeconds.toFixed(6)),scrubberSeconds:Number(boundedDisplay().toFixed(6)),missionTimeHours:STORY.mission_time_hours,cueIndex:s.index,cuePhase:Number(s.phase.toFixed(6)),segment:s.segment,segmentPhase:Number(s.segmentPhase.toFixed(6)),sourceEventHash:s.cue.source_event_hash,cueMissionStartHours:tr.mission_time_start_hours,cueMissionEndHours:tr.mission_time_end_hours,cueDeltaToCurrentHours:tr.mission_time_delta_to_current_hours,temporalRelation:tr.temporal_relation,wallClockAgeStatus:tr.wall_clock_age_status,futureReceiptStatus:STORY.temporal_reconstruction.future_receipt_status,stateChangeReceiptStatus:s.cue.state_change_receipt?.status||'UNKNOWN',eventDeltaCount:changes.length,cameraPreset,labelMode,inspectedPlanetId:inspectedId,inspectorFollowsEvent:inspectPlanetId==='',authority:'presentation_state_only',mayAdvanceMissionTime:false,mayAppendEvent:false,mayChangeTruthLabels:false,mayRetargetEvent:false,mayModifyRuntimeResources:false};
}
function metric(k,v){return`<div class="metric"><span>${esc(k)}</span><b>${esc(v)}</b></div>`}
const RESOURCE_LABELS={mission_time_hours:'mission time',reactor_reserve_percent:'reactor reserve',sensor_health_percent:'sensor health',hull_integrity_percent:'hull integrity',heat_percent:'heat',knowledge_points:'knowledge'};
function boundedDisplay(){if(!TOTAL_DISPLAY_SECONDS)return 0;return $('autoAdvance').checked?((displaySeconds%TOTAL_DISPLAY_SECONDS)+TOTAL_DISPLAY_SECONDS)%TOTAL_DISPLAY_SECONDS:clamp(displaySeconds,0,MAX_SCRUB_SECONDS)}
function deltaText(row){if(!finite(row.delta))return'UNKNOWN';const n=Number(row.delta),sign=n>0?'+':'';const units={hours:' h',percent_points:' pp',points:' points',source_unit_unspecified:''};return`${sign}${n}${units[row.unit]??` ${row.unit}`}`}
function deltaScale(resourceId){const values=STORY.cues.flatMap(cue=>cue.state_change_receipt?.changes||[]).filter(row=>row.resource_id===resourceId&&finite(row.delta)).map(row=>Math.abs(Number(row.delta)));return Math.max(...values,1e-9)}
function updatePanels(s){
  selectedCue=s.index;$('cueSelect').value=String(s.index);
  const tr=s.cue.temporal_receipt||{},relation=tr.temporal_relation==='ledger_head'?'LEDGER HEAD':'HISTORICAL RECEIPT',relationClass=tr.temporal_relation==='ledger_head'?'head':'history',scrubSeconds=boundedDisplay(),inspectedId=inspectPlanetId||s.cue.target_planet_id,planet=STORY.planets.find(p=>p.planet_id===inspectedId),eventTarget=STORY.planets.find(p=>p.planet_id===s.cue.target_planet_id),isEventTarget=inspectedId===s.cue.target_planet_id,changes=s.cue.state_change_receipt?.changes||[];
  $('phaseLabel').textContent=s.segment.replaceAll('_',' ');$('cueHeadline').textContent=`Turn ${s.cue.turn} · ${s.cue.outcome_title||s.cue.outcome_id}`;$('framingLabel').textContent=`${cameraPreset.replaceAll('_',' ')} · ${labelMode} labels · inspect ${planet?.name||'unknown'}`;$('missionClockLabel').textContent=formatMission(STORY.mission_time_hours);$('displayClockLabel').textContent=`${String(Math.floor(displaySeconds/60)).padStart(2,'0')}:${(displaySeconds%60).toFixed(1).padStart(4,'0')}`;
  $('replayScrubber').value=String(scrubSeconds);$('scrubLabel').textContent=`${String(Math.floor(scrubSeconds/60)).padStart(2,'0')}:${(scrubSeconds%60).toFixed(1).padStart(4,'0')} · receipt ${s.index+1}`;$('inspectSelect').value=inspectPlanetId;
  $('playToggle').textContent=playing?'Pause causal playback':'Start causal playback';$('playToggle').setAttribute('aria-pressed',String(playing));$('statusLine').innerHTML=`<strong class="${playing?'ok':'hold'}">${playing?'PLAYING':'PAUSED'}</strong><p class="fine">${esc(s.segment.replaceAll('_',' '))} · replay phase ${s.phase.toFixed(3)} · frame ${frameCount}. Presentation state only.</p>`;
  $('eventPanel').innerHTML=`<p class="eventTitle">${esc(s.cue.action)}</p><span class="truthType">${esc(s.cue.observation_truth_type)}</span><p class="eventText">${esc(s.cue.observation)}</p><span class="truthType">${esc(s.cue.interpretation_truth_type)}</span><p class="eventText">${esc(s.cue.interpretation)}</p><p class="fine mono">${esc(s.cue.source_event_hash)}</p>`;
  $('temporalPanel').innerHTML=`<span class="stateTag ${relationClass}">${relation}</span>`+metric('receipt range',`${formatMission(tr.mission_time_start_hours)} → ${formatMission(tr.mission_time_end_hours)}`)+metric('recorded duration',finite(tr.mission_duration_hours)?`${tr.mission_duration_hours} h`:'UNKNOWN')+metric('Δ to current',formatDelta(tr.mission_time_delta_to_current_hours))+`<span class="stateTag unknown">AGE UNKNOWN</span><p class="fine mono">${esc(tr.wall_clock_age_status)}</p><p class="fine">No future receipt is imported; that is not a prediction about what happens next.</p>`;
  $('signalPanel').innerHTML=metric('one-way light time',`${s.cue.one_way_light_time_s} s`)+metric('transmit duration',`${s.cue.transmit_duration_s} s`)+metric('earliest full response',`${s.cue.earliest_full_response_s} s`)+`<p class="fine">Displayed timing is compressed and cannot prove delivery or acceptance.</p>`;
  $('deltaPanel').innerHTML=changes.length?`<div class="deltaGrid">${changes.map(row=>{const width=finite(row.delta)?Math.max(3,Math.abs(Number(row.delta))/deltaScale(row.resource_id)*100):0;return`<div class="deltaRow"><div class="deltaMeta"><span>${esc(RESOURCE_LABELS[row.resource_id]||row.resource_id)}</span><b>${esc(deltaText(row))}</b></div><div class="deltaTrack" aria-hidden="true"><div class="deltaFill ${esc(row.direction)}" style="width:${width}%"></div></div></div>`}).join('')}</div><p class="fine">Each bar compares that resource only with its own largest absolute change in the imported ledger. Cyan means increase and violet means decrease; neither assigns good or bad.</p><p class="fine mono">${esc(s.cue.state_change_receipt?.truth_type||changes[0]?.truth_type||'recorded-simulation-event-delta')}</p>`:'<p class="fine">No recorded resource deltas in this receipt.</p>';
  $('targetPanel').innerHTML=planet?`<span class="stateTag ${isEventTarget?'head':'inspect'}">${isEventTarget?'EVENT TARGET':'INSPECT ONLY'}</span>`+metric('object',planet.name)+metric('event target',eventTarget?.name||'UNKNOWN')+metric('kind',planet.kind)+metric('semi-major axis',`${planet.semi_major_axis_au} AU`)+metric('axis truth',planet.semi_major_axis_truth_type)+metric('orbital period',`${planet.orbital_period_days} d`)+metric('period truth',planet.orbital_period_truth_type)+`<p class="fine">Inspector selection changes framing and facts only; it cannot retarget the recorded event.</p>`:'<p class="fine">Object unavailable.</p>';
  for(const [i,node] of [...$('timeline').children].entries()){node.classList.toggle('active',i===s.index);node.setAttribute('aria-current',i===s.index?'step':'false')}canvas.setAttribute('aria-label',`Turn ${s.cue.turn}, ${s.segment.replaceAll('_',' ')}, receipt ${formatMission(tr.mission_time_start_hours)} to ${formatMission(tr.mission_time_end_hours)}, inspecting ${planet?.name||'unknown'}, ${cameraPreset.replaceAll('_',' ')} camera`)
}
function loop(timestamp){if(!playing){rafId=null;lastTime=null;return}if(lastTime==null)lastTime=timestamp;const delta=clamp((timestamp-lastTime)/1000,0,.1);lastTime=timestamp;displaySeconds+=delta*speed();frameCount+=1;draw();rafId=requestAnimationFrame(loop)}
function setPlaying(next,reason='user_control'){if(Boolean(next)&&reduced){playing=false;lastTime=null;draw();return false}playing=Boolean(next);lastTime=null;if(rafId!=null){cancelAnimationFrame(rafId);rafId=null}if(playing)rafId=requestAnimationFrame(loop);else draw();return playing}
function reset(){setPlaying(false,'reset');displaySeconds=0;frameCount=0;selectedCue=0;$('cueSelect').value='0';draw()}
function selectCue(index){const i=Math.max(0,Math.min(STORY.cues.length-1,Number(index)||0));selectedCue=i;displaySeconds=i*CUE_SECONDS;$('autoAdvance').checked=false;draw()}
function previousCue(){selectCue((selectedCue-1+STORY.cues.length)%STORY.cues.length);return selectedCue}
function nextCue(){selectCue((selectedCue+1)%STORY.cues.length);return selectedCue}
function scrubTo(value){setPlaying(false,'scrubber');displaySeconds=clamp(Number(value)||0,0,MAX_SCRUB_SECONDS);selectedCue=Math.max(0,Math.min(STORY.cues.length-1,Math.floor(displaySeconds/CUE_SECONDS)));$('autoAdvance').checked=true;draw();return displaySeconds}
function setReducedMotion(next){reduced=Boolean(next);$('reducedMotion').checked=reduced;if(reduced)setPlaying(false,'reduced_motion');else draw();return reduced}
function setCamera(value){const allowed=STORY.presentation_profiles.camera_presets.map(row=>row.id);cameraPreset=allowed.includes(value)?value:STORY.presentation_profiles.default_camera_preset;$('cameraSelect').value=cameraPreset;draw();return cameraPreset}
function setLabels(value){labelMode=STORY.presentation_profiles.label_modes.includes(value)?value:STORY.presentation_profiles.default_label_mode;$('labelSelect').value=labelMode;draw();return labelMode}
function setInspector(value){const allowed=STORY.planets.map(row=>row.planet_id);inspectPlanetId=allowed.includes(value)?value:'';$('inspectSelect').value=inspectPlanetId;draw();return inspectPlanetId}
function cycleCamera(){const values=STORY.presentation_profiles.camera_presets.map(row=>row.id),index=values.indexOf(cameraPreset);return setCamera(values[(index+1)%values.length])}
function cycleInspector(){const values=['',...STORY.planets.map(row=>row.planet_id)],index=values.indexOf(inspectPlanetId);return setInspector(values[(index+1)%values.length])}
function init(){
  $('cueSelect').innerHTML=STORY.cues.map((c,i)=>`<option value="${i}">Turn ${c.turn} · ${esc(c.outcome_title||c.outcome_id)}</option>`).join('');
  $('cameraSelect').innerHTML=STORY.presentation_profiles.camera_presets.map(row=>`<option value="${esc(row.id)}">${esc(row.label)}</option>`).join('');$('cameraSelect').value=cameraPreset;$('labelSelect').value=labelMode;
  $('inspectSelect').innerHTML=`<option value="">Follow event target</option>`+STORY.planets.map(row=>`<option value="${esc(row.planet_id)}">${esc(row.name)} · inspect only</option>`).join('');$('inspectSelect').value=inspectPlanetId;$('replayScrubber').max=String(MAX_SCRUB_SECONDS);
  $('timeline').innerHTML=STORY.cues.map((c,i)=>{const tr=c.temporal_receipt||{},head=tr.temporal_relation==='ledger_head';return`<button type="button" class="${head?'head':''}" data-cue="${i}"><b>Turn ${c.turn}</b><small>${esc(c.outcome_title||c.outcome_id)}</small><small class="timeRange">${formatMission(tr.mission_time_start_hours)} → ${formatMission(tr.mission_time_end_hours)}</small><div class="timelineState">${head?'ledger head':`${formatDelta(tr.mission_time_delta_to_current_hours)} to current`}</div></button>`}).join('');$('timeline').querySelectorAll('button').forEach(btn=>btn.addEventListener('click',()=>selectCue(btn.dataset.cue)));
  $('sourcePanel').innerHTML=metric('repository',IMPORT.source_repository)+metric('commit',IMPORT.source_commit.slice(0,12))+metric('events',IMPORT.event_count)+metric('adapter gate',IMPORT.status)+metric('time reconstruction',STORY.temporal_reconstruction.status)+`<p class="fine">Selected hashes and ledger links passed. Main semantic verification remains required before merge.</p>`;
  $('resources').innerHTML=Object.entries(STORY.current_resources).filter(([k])=>RESOURCE_LABELS[k]&&k!=='mission_time_hours').map(([k,v])=>`<div class="resource"><b>${esc(v)}${k.endsWith('_percent')?'%':''}</b><span>${esc(RESOURCE_LABELS[k])}</span></div>`).join('');
  reduced=Boolean(window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches);$('reducedMotion').checked=reduced;
  $('playToggle').addEventListener('click',()=>setPlaying(!playing));$('previousCue').addEventListener('click',previousCue);$('nextCue').addEventListener('click',nextCue);$('resetButton').addEventListener('click',reset);$('replayScrubber').addEventListener('input',e=>scrubTo(e.target.value));$('cueSelect').addEventListener('change',e=>selectCue(e.target.value));$('cameraSelect').addEventListener('change',e=>setCamera(e.target.value));$('inspectSelect').addEventListener('change',e=>setInspector(e.target.value));$('labelSelect').addEventListener('change',e=>setLabels(e.target.value));$('speedSelect').addEventListener('change',draw);$('autoAdvance').addEventListener('change',draw);$('reducedMotion').addEventListener('change',e=>setReducedMotion(e.target.checked));
  canvas.addEventListener('keydown',e=>{if(e.code==='Space'){e.preventDefault();setPlaying(!playing)}if(e.code==='ArrowRight'){e.preventDefault();nextCue()}if(e.code==='ArrowLeft'){e.preventDefault();previousCue()}if(e.code==='KeyC'){e.preventDefault();cycleCamera()}if(e.code==='KeyI'){e.preventDefault();cycleInspector()}});document.addEventListener('visibilitychange',()=>{if(document.hidden)setPlaying(false,'page_hidden')});window.addEventListener('resize',fit);fit()
}
window.__axmMainBridgeControl={setPlaying,reset,selectCue,previousCue,nextCue,scrubTo,setReducedMotion,setCamera,setLabels,setInspector,cycleCamera,cycleInspector,sample:()=>sample(),draw};init();
</script>
</body></html>'''


def render_temporal_bridge(storyboard: dict[str, Any], import_receipt: dict[str, Any]) -> str:
    if storyboard.get("schema") != "axm.main-simulator-temporal-storyboard.v1":
        raise ValueError("unsupported storyboard schema")
    if import_receipt.get("status") != "IMPORT_VALID":
        raise ValueError("renderer requires a valid main-simulator import receipt")
    if not storyboard.get("cues"):
        raise ValueError("renderer requires at least one immutable event cue")
    profiles = storyboard.get("presentation_profiles", {})
    if not profiles.get("camera_presets") or not profiles.get("label_modes"):
        raise ValueError("renderer requires bounded presentation profiles")
    payload = json.dumps(storyboard, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    receipt = json.dumps(import_receipt, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    title = html.escape(str(storyboard.get("system_name", "AXM Temporal Bridge")))
    return (
        _TEMPLATE.replace("__AXM_TITLE__", title)
        .replace("__AXM_STORYBOARD__", payload)
        .replace("__AXM_RECEIPT__", receipt)
    )
