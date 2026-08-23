/* v0.10 post-clearance recovery: residual truth before safe-state release */
const POST_CLEARANCE_RECOVERY=STORY.post_clearance_recovery||{contracts:[],contract_count:0};
function recoveryContracts(){return Array.isArray(POST_CLEARANCE_RECOVERY.contracts)?POST_CLEARANCE_RECOVERY.contracts:[]}
function activeRecoveryContract(){
  const p=typeof activeProcedure==='function'?activeProcedure():null;
  if(!p)return null;
  return recoveryContracts().find(row=>row.source_failure_id===p.source_failure_id)||null;
}
function ensurePostClearanceRecoveryPanel(){
  if($('postClearanceRecovery'))return;
  const anchor=$('faultClearanceApply');
  if(!anchor)return;
  anchor.insertAdjacentHTML('afterend','<div class="recoveryDivider"></div><h2>Post-clearance recovery · explicit release</h2><div id="postClearanceRecovery" class="postClearanceRecoveryPanel"><div class="mini">Select a failure procedure to inspect the residual-state and safe-state-exit contract.</div></div>');
}
function renderPostClearanceRecoveryPanel(){
  const panel=$('postClearanceRecovery');if(!panel)return;
  const c=activeRecoveryContract();
  if(!c){
    panel.innerHTML='<div class="mini">v0.10 separates verified fault clearance from recovery. Fault cleared does not mean resources, health, load sheds, crew state, or safe-state restrictions are automatically restored.</div>';
    return;
  }
  const ready=c.status==='RECOVERY_ENGINE_AVAILABLE_AFTER_APPLIED_VERIFIED_CLEARANCE';
  const inputs=(c.required_inputs||[]).map(v=>`<span>${escHtml(v.replaceAll('_',' '))}</span>`).join('');
  panel.innerHTML=`<div class="recoveryTitle" style="color:${ready?'#78f3b4':'#ffd078'}">${escHtml(c.source_failure_id)}</div>
    <div class="recoveryMeta"><span class="tag ${ready?'info':'hold'}">${escHtml(c.status)}</span><span class="tag hold">MISSION COMMANDER RELEASE</span></div>
    <div class="recoveryFlow">
      <div><b>FAULT CLEARED</b><small>verified clearance receipt</small></div>
      <i>→</i><div><b>RECOVERY INCOMPLETE</b><small>assess residual state</small></div>
      <i>→</i><div><b>DEGRADED SAFE / NOMINAL</b><small>independent evidence gate</small></div>
      <i>→</i><div><b>RECOVERY VERIFIED</b><small>explicit safe-state exit only</small></div>
    </div>
    <div class="recoveryInputs">${inputs}</div>
    <div class="recoveryBoundary">Release may change the safe-state mode only. Existing load sheds, resources, crew state, structural condition, system health, and unrelated faults remain as observed until separately changed by authoritative simulation actions.</div>
    <div class="recoveryPolicy"><b>Candidate policy</b><span>${escHtml(c.authority_policy_id||'policy unavailable')}</span><small>${escHtml(c.candidate_authority_policy?.truth_status||'UNKNOWN')}</small></div>
    <div class="recoveryLock">RENDERER LOCKED · no automatic recovery · no inferred restoration · no safe-state exit without a live assessment and commander authorization</div>`;
}
function drawPostClearanceRecoveryOverlay(){
  const c=activeRecoveryContract();if(!c)return;
  if(typeof repairStageIndex!=='undefined'&&repairStageIndex!==4)return;
  const ready=c.status==='RECOVERY_ENGINE_AVAILABLE_AFTER_APPLIED_VERIFIED_CLEARANCE';
  X.save();X.globalAlpha=.94;X.fillStyle='#02070be6';X.fillRect(102,228,312,30);X.strokeStyle=ready?'#78f3b4':'#ffd078';X.strokeRect(102,228,312,30);
  text('FAULT CLEARANCE ≠ FULL RECOVERY',258,237,ready?'#78f3b4':'#ffd078',5,'center');
  text('residual evidence → commander release → safe-state exit',258,247,'#b9cbd4',4,'center');
  text('resources + load sheds remain observed',258,254,'#7f9aa8',4,'center');X.restore();
}
function extendPostClearanceRecoveryRuntime(){
  const runtime=window.__axmLowPixelBridge;if(!runtime)return;const c=activeRecoveryContract();
  Object.assign(runtime,{
    postClearanceRecoveryVersion:'0.10.0-candidate',
    postClearanceRecoveryContractCount:POST_CLEARANCE_RECOVERY.contract_count??recoveryContracts().length,
    postClearanceRecoveryContractId:c?.contract_id||null,
    postClearanceRecoveryStatus:c?.status||null,
    postClearanceRecoveryAuthorityPolicy:c?.candidate_authority_policy?.truth_status||null,
    rendererMayApplySafeStateExit:false,
    rendererMayRestoreResources:false,
    rendererMayRestoreSystemHealth:false,
    rendererMayRemoveLoadSheds:false,
    safeStateExited:false
  });
}
ensurePostClearanceRecoveryPanel();
const drawV08Recovery=draw;
draw=function(){drawV08Recovery();ensurePostClearanceRecoveryPanel();drawPostClearanceRecoveryOverlay();renderPostClearanceRecoveryPanel();extendPostClearanceRecoveryRuntime()}
window.__axmLowPixelBridgeControl.activePostClearanceRecoveryContract=activeRecoveryContract;
draw();
