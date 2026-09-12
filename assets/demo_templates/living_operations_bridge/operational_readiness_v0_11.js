/* v0.11 truthful operating mode + non-executable capability envelope */
const OPERATIONAL_READINESS=STORY.operational_readiness||{contracts:[],contract_count:0};
function operationalReadinessContracts(){return Array.isArray(OPERATIONAL_READINESS.contracts)?OPERATIONAL_READINESS.contracts:[]}
function activeOperationalReadinessContract(){
  const p=typeof activeProcedure==='function'?activeProcedure():null;
  if(!p)return null;
  return operationalReadinessContracts().find(row=>row.source_failure_id===p.source_failure_id)||null;
}
function ensureOperationalReadinessPanel(){
  if($('operationalReadiness'))return;
  const anchor=$('postClearanceRecovery');
  if(!anchor)return;
  anchor.insertAdjacentHTML('afterend','<div class="readinessDivider"></div><h2>Operational readiness · truthful final mode</h2><div id="operationalReadiness" class="operationalReadinessPanel"><div class="mini">Select a failure procedure to inspect the final operating-mode and capability-envelope contract.</div></div>');
}
function renderOperationalReadinessPanel(){
  const panel=$('operationalReadiness');if(!panel)return;
  const c=activeOperationalReadinessContract();
  if(!c){
    panel.innerHTML='<div class="mini">v0.11 prevents a cleared emergency from silently becoming “nominal.” Residual state produces DEGRADED OPERATIONS; nominal requires no residual indicators. The capability envelope is inspection-only.</div>';
    return;
  }
  const ready=c.status==='OPERATIONAL_RELEASE_ENGINE_AVAILABLE_AFTER_VERIFIED_RECOVERY_CHAIN';
  const inputs=(c.required_inputs||[]).map(v=>`<span>${escHtml(v.replaceAll('_',' '))}</span>`).join('');
  panel.innerHTML=`<div class="readinessTitle" style="color:${ready?'#78f3b4':'#ffd078'}">${escHtml(c.source_failure_id)}</div>
    <div class="readinessMeta"><span class="tag ${ready?'info':'hold'}">${escHtml(c.status)}</span><span class="tag hold">NOMINAL IS NOT A DEFAULT</span></div>
    <div class="readinessFlow">
      <div><b>SAFE STATE RELEASED</b><small>validated recovery chain</small></div>
      <i>→</i><div><b>RESIDUAL CHECK</b><small>authoritative state replay</small></div>
      <i>→</i><div><b>DEGRADED OPERATIONS / NOMINAL</b><small>truthful final mode</small></div>
      <i>→</i><div><b>CAPABILITY ENVELOPE</b><small>available · limited · hold</small></div>
    </div>
    <div class="readinessInputs">${inputs}</div>
    <div class="readinessModes"><div><b>Residuals present</b><span>${escHtml(c.mode_policy?.residuals_present||'degraded_operations')}</span></div><div><b>No residuals</b><span>${escHtml(c.mode_policy?.no_residuals_present||'nominal')}</span></div></div>
    <div class="readinessBoundary">The final release may classify operating mode and expose bounded operation readiness only. It does not restore resources, remove load sheds, repair system health, clear unrelated faults, execute an operation, or override a hold.</div>
    <div class="readinessPolicy"><b>Candidate policy</b><span>${escHtml(c.authority_policy_id||'policy unavailable')}</span><small>${escHtml(c.mode_policy?.truth_status||'UNKNOWN')}</small></div>
    <div class="readinessLock">RENDERER LOCKED · no mode classification · no operational release · no action execution · no nominal claim while residuals remain</div>`;
}
function drawOperationalReadinessOverlay(){
  const c=activeOperationalReadinessContract();if(!c)return;
  if(typeof repairStageIndex!=='undefined'&&repairStageIndex!==4)return;
  const ready=c.status==='OPERATIONAL_RELEASE_ENGINE_AVAILABLE_AFTER_VERIFIED_RECOVERY_CHAIN';
  X.save();X.globalAlpha=.94;X.fillStyle='#02070be6';X.fillRect(102,172,312,26);X.strokeStyle=ready?'#78f3b4':'#ffd078';X.strokeRect(102,172,312,26);
  text('NOMINAL IS NOT A DEFAULT',258,181,ready?'#78f3b4':'#ffd078',5,'center');
  text('residuals → DEGRADED OPERATIONS → capability envelope',258,190,'#b9cbd4',4,'center');
  text('inspection only · execution remains locked',258,196,'#7f9aa8',4,'center');X.restore();
}
function extendOperationalReadinessRuntime(){
  const runtime=window.__axmLowPixelBridge;if(!runtime)return;const c=activeOperationalReadinessContract();
  Object.assign(runtime,{
    operationalReadinessVersion:'0.11.0-candidate',
    operationalReadinessContractCount:OPERATIONAL_READINESS.contract_count??operationalReadinessContracts().length,
    operationalReadinessContractId:c?.contract_id||null,
    operationalReadinessStatus:c?.status||null,
    operationalReadinessPolicyStatus:c?.mode_policy?.truth_status||null,
    rendererMayApplyOperationalRelease:false,
    rendererMayClassifyOperatingMode:false,
    rendererMayExecuteOperation:false,
    rendererMayOverrideOperationalHold:false,
    rendererMayClaimNominalWithResiduals:false,
    operationallyReleased:false
  });
}
ensureOperationalReadinessPanel();
const drawV10Readiness=draw;
draw=function(){drawV10Readiness();ensureOperationalReadinessPanel();drawOperationalReadinessOverlay();renderOperationalReadinessPanel();extendOperationalReadinessRuntime()}
window.__axmLowPixelBridgeControl.activeOperationalReadinessContract=activeOperationalReadinessContract;
draw();
