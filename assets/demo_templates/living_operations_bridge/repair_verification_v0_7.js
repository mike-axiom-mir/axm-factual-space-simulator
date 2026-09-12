/* v0.7 repair attempt + post-repair verification gate: no runtime authority */
const REPAIR_GATES=STORY.repair_verification||{gates:[],gate_count:0};
let repairStageIndex=0;
const REPAIR_STAGE_LABELS=['procedure receipt','repair plan','external execution','post-repair verification','authoritative clearance'];
function repairGateRows(){return Array.isArray(REPAIR_GATES.gates)?REPAIR_GATES.gates:[]}
function activeRepairGate(){
  const p=typeof activeProcedure==='function'?activeProcedure():null;
  if(!p)return null;
  return repairGateRows().find(row=>row.source_failure_id===p.source_failure_id)||null;
}
function ensureRepairVerificationPanel(){
  if($('repairVerification'))return;
  const anchor=$('damageTopology');
  anchor.insertAdjacentHTML('afterend','<hr style="border:0;border-top:1px solid #17303e;margin:12px 0"><h2>Repair attempt + verification gate</h2><div id="repairVerification" class="repairVerificationPanel"><div class="mini">Select a failure procedure to inspect the receipt chain required before fault clearance can even become eligible.</div></div><div id="repairStageControls" class="repairStageControls"><button id="repairStagePrev" type="button">Previous gate</button><button id="repairStageNext" type="button">Next gate</button></div>');
}
function setRepairStage(i){repairStageIndex=(Number(i)+REPAIR_STAGE_LABELS.length)%REPAIR_STAGE_LABELS.length;draw();return repairStageIndex}
function renderRepairVerificationPanel(){
  const gate=activeRepairGate();
  if(!gate){$('repairVerification').innerHTML='<div class="mini">The simulator already has maintenance, procedure and topology organs. v0.7 joins them with explicit external execution + post-repair verification receipts.</div>';$('repairStageControls').style.display='none';return}
  $('repairStageControls').style.display='grid';
  const ready=gate.status==='READY_FOR_EXTERNAL_REPAIR_PLAN';
  const ladder=REPAIR_STAGE_LABELS.map((label,i)=>`<span class="${i===repairStageIndex?'active ':''}${!ready&&i>0?'hold':''}">${i+1}. ${escHtml(label)}</span>`).join('');
  const path=gate.preferred_room_path?.rooms?.map(v=>escHtml(v)).join(' → ')||'NO PINNED ROOM PATH';
  $('repairVerification').innerHTML=`<div class="repairGateTitle" style="color:${ready?'#78f3b4':'#ffd078'}">${escHtml(gate.source_failure_id)}</div>
    <div class="repairGateMeta"><span class="tag ${ready?'info':'hold'}">${escHtml(gate.status)}</span><span class="tag info">${escHtml(gate.source_system_id||'unknown system')}</span></div>
    <div class="repairLadder">${ladder}</div>
    <div class="mini">mapped access: ${path}</div>
    <div class="repairGateBoundary">${ready?'A sourced repair plan may be staged by the engine after a completed procedure session. External execution still needs its own receipt, and an effective result still needs independent post-repair verification before clearance eligibility.':`HOLD: ${escHtml(gate.hold_reason||'repair gate prerequisites not met')}`}</div>
    <div class="mini">Current bridge view never executes the repair, consumes a spare, validates a fabricated part, modifies runtime, or clears the fault.</div>`;
}
function drawRepairVerificationOverlay(){
  const gate=activeRepairGate();if(!gate)return;
  const ready=gate.status==='READY_FOR_EXTERNAL_REPAIR_PLAN',x0=131,y=244,span=55;
  X.save();X.globalAlpha=.92;X.fillStyle='#02070be6';X.fillRect(112,229,292,35);X.strokeStyle=ready?'#78f3b4':'#ffd078';X.strokeRect(112,229,292,35);
  text('REPAIR EVIDENCE GATE · FAULT NOT CLEARED',258,237,ready?'#78f3b4':'#ffd078',5,'center');
  for(let i=0;i<5;i++){const x=x0+i*span;if(i)line({x:x-span+5,y},{x:x-5,y},'#55798a',1);X.strokeStyle=i===repairStageIndex?'#78f3b4':'#55798a';X.strokeRect(x-5,y-5,10,10);text(String(i+1),x,y+2,i===repairStageIndex?'#dffff0':'#91aab7',4,'center')}
  X.restore();
}
function extendRepairVerificationRuntime(){
  const runtime=window.__axmLowPixelBridge;if(!runtime)return;const gate=activeRepairGate();
  Object.assign(runtime,{
    repairVerificationVersion:'0.7.0-candidate',
    repairVerificationGateCount:REPAIR_GATES.gate_count??repairGateRows().length,
    repairVerificationGateId:gate?.gate_id||null,
    repairVerificationGateStatus:gate?.status||null,
    repairVerificationStageIndex:repairStageIndex,
    repairVerificationStage:REPAIR_STAGE_LABELS[repairStageIndex],
    repairVerificationAuthority:'presentation_of_engine_gate_only',
    externalExecutionRecorded:false,
    verificationComplete:false,
    repairVerified:false,
    faultClearanceEligible:false,
    faultCleared:false,
    mayExecuteRepair:false,
    mayConsumeSpares:false,
    mayFabricateRepairPart:false,
    mayModifyRuntime:false,
    mayClearFault:false
  });
}
ensureRepairVerificationPanel();
const drawV06Repair=draw;
draw=function(){drawV06Repair();drawRepairVerificationOverlay();renderRepairVerificationPanel();extendRepairVerificationRuntime()}
$('repairStagePrev').addEventListener('click',()=>setRepairStage(repairStageIndex-1));
$('repairStageNext').addEventListener('click',()=>setRepairStage(repairStageIndex+1));
window.__axmLowPixelBridgeControl.activeRepairVerificationGate=activeRepairGate;
window.__axmLowPixelBridgeControl.setRepairVerificationStage=setRepairStage;
draw();
