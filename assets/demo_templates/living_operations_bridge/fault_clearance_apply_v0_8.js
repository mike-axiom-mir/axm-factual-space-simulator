/* v0.8 authoritative fault-clearance apply boundary: engine exists, renderer remains locked */
const CLEARANCE_APPLY=STORY.fault_clearance_apply||{contracts:[],contract_count:0};
function clearanceContracts(){return Array.isArray(CLEARANCE_APPLY.contracts)?CLEARANCE_APPLY.contracts:[]}
function activeClearanceContract(){
  const p=typeof activeProcedure==='function'?activeProcedure():null;
  if(!p)return null;
  return clearanceContracts().find(row=>row.source_failure_id===p.source_failure_id)||null;
}
function ensureClearanceApplyPanel(){
  if($('faultClearanceApply'))return;
  const anchor=$('repairStageControls');
  anchor.insertAdjacentHTML('afterend','<hr style="border:0;border-top:1px solid #17303e;margin:12px 0"><h2>Authoritative fault clearance · renderer locked</h2><div id="faultClearanceApply" class="faultClearanceApplyPanel"><div class="mini">Select a failure procedure to inspect the final authoritative state-apply contract.</div></div>');
}
function renderClearanceApplyPanel(){
  const c=activeClearanceContract();
  if(!c){$('faultClearanceApply').innerHTML='<div class="mini">v0.8 connects verified repair evidence back to the existing axm.ship-state.v1 engine. The bridge can display that contract but cannot execute it.</div>';return}
  const ready=c.status==='ENGINE_AVAILABLE_REQUIRES_VERIFIED_CANDIDATE_AND_LIVE_SHIP_STATE';
  const inputs=(c.required_inputs||[]).map(v=>`<span>${escHtml(v.replaceAll('_',' '))}</span>`).join('');
  $('faultClearanceApply').innerHTML=`<div class="clearanceTitle" style="color:${ready?'#78f3b4':'#ffd078'}">${escHtml(c.source_failure_id)}</div>
    <div class="clearanceMeta"><span class="tag ${ready?'info':'hold'}">${escHtml(c.status)}</span><span class="tag info">${escHtml(c.command_level||'unknown authority')}</span></div>
    <div class="clearanceInputs">${inputs}</div>
    <div class="clearancePolicy"><b>Candidate authority policy</b><span>${escHtml(c.primary_role_id||'primary role unresolved')} · ${escHtml(c.authority_policy_id||'policy unavailable')}</span><small>${escHtml(c.candidate_authority_policy?.truth_status||'UNKNOWN')}</small></div>
    <div class="clearanceBoundary">The authoritative engine may remove only the verified active fault and reconcile only evidence-covered state paths. It cannot infer restored values, clear unrelated faults, or silently exit safe state.</div>
    <div class="clearanceLock">RENDERER LOCKED · live axm.ship-state.v1 + verified candidate + authorization + exact reconciliation required</div>`;
}
function drawClearanceApplyOverlay(){
  const c=activeClearanceContract();if(!c)return;
  const ready=c.status==='ENGINE_AVAILABLE_REQUIRES_VERIFIED_CANDIDATE_AND_LIVE_SHIP_STATE';
  if(typeof repairStageIndex!=='undefined'&&repairStageIndex!==4)return;
  X.save();X.globalAlpha=.94;X.fillStyle='#02070be6';X.fillRect(102,201,312,24);X.strokeStyle=ready?'#78f3b4':'#ffd078';X.strokeRect(102,201,312,24);
  text('AUTHORITATIVE CLEARANCE APPLY · RENDERER LOCKED',258,210,ready?'#78f3b4':'#ffd078',5,'center');
  text('verified candidate + live state hash + authority + exact reconciliation',258,219,'#b9cbd4',4,'center');X.restore();
}
function extendClearanceApplyRuntime(){
  const runtime=window.__axmLowPixelBridge;if(!runtime)return;const c=activeClearanceContract();
  Object.assign(runtime,{
    faultClearanceApplyVersion:'0.8.0-candidate',
    faultClearanceApplyContractCount:CLEARANCE_APPLY.contract_count??clearanceContracts().length,
    faultClearanceApplyContractId:c?.contract_id||null,
    faultClearanceApplyStatus:c?.status||null,
    authoritativeClearanceEnginePresent:Boolean(c),
    clearanceAuthorityPolicyStatus:c?.candidate_authority_policy?.truth_status||null,
    rendererMayApplyFaultClearance:false,
    rendererMayModifyShipState:false,
    rendererMayInferRestoredValues:false,
    rendererMayClearUnrelatedFaults:false,
    faultCleared:false
  });
}
ensureClearanceApplyPanel();
const drawV07Clearance=draw;
draw=function(){drawV07Clearance();drawClearanceApplyOverlay();renderClearanceApplyPanel();extendClearanceApplyRuntime()}
window.__axmLowPixelBridgeControl.activeFaultClearanceApplyContract=activeClearanceContract;
draw();
