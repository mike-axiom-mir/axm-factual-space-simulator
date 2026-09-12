/* v0.6 damage topology + repair-access overlay: derived view only */
const DAMAGE_TOPOLOGY=STORY.damage_topology||{topologies:[],topology_count:0};
function topologyRows(){return Array.isArray(DAMAGE_TOPOLOGY.topologies)?DAMAGE_TOPOLOGY.topologies:[]}
function activeTopology(){
  const p=typeof activeProcedure==='function'?activeProcedure():null;
  if(!p)return null;
  return topologyRows().find(row=>row.source_failure_id===p.source_failure_id)||null;
}
function ensureTopologyPanel(){
  if($('damageTopology'))return;
  const anchor=$('failureProcedureControls');
  anchor.insertAdjacentHTML('afterend','<hr style="border:0;border-top:1px solid #17303e;margin:12px 0"><h2>Damage topology · derived existing graphs</h2><div id="damageTopology" class="damageTopologyPanel"><div class="mini">Select a failure procedure to inspect system interfaces, mapped rooms and repair access.</div></div>');
}
function topologyColor(row){
  return row?.source_criticality==='crew_survival'?'#ff736f':row?.source_criticality==='high'?'#ffd078':'#63e8ff';
}
function shortNode(id){const s=String(id||'?').replaceAll('_',' ');return s.length>14?s.slice(0,13)+'…':s}
function drawDamageTopologyOverlay(){
  const row=activeTopology(); if(!row)return;
  const color=topologyColor(row), edges=Array.isArray(row.direct_interfaces)?row.direct_interfaces.slice(0,4):[];
  const cx=401,cy=105;
  X.save();
  X.globalAlpha=.9;X.fillStyle='#02070be6';X.fillRect(333,76,140,77);X.strokeStyle=color;X.strokeRect(333,76,140,77);
  text('DERIVED TOPOLOGY',401,84,'#63e8ff',5,'center');
  X.fillStyle=color;X.fillRect(cx-13,cy-6,26,12);text(shortNode(row.source_system_id).slice(0,8).toUpperCase(),cx,cy+2,'#02040a',5,'center');
  const pts=[{x:351,y:92},{x:451,y:92},{x:351,y:128},{x:451,y:128}];
  edges.forEach((edge,i)=>{const p=pts[i];line({x:cx,y:cy},p,'#55798a',1);X.strokeStyle='#55798a';X.strokeRect(p.x-11,p.y-5,22,10);text(shortNode(edge.neighbor_system_id).slice(0,7).toUpperCase(),p.x,p.y+2,'#b9cbd4',4,'center')});
  const access=row.access||{},path=access.preferred_room_path?.rooms||[];
  text(access.status||'ACCESS UNKNOWN',401,142,String(access.status||'').startsWith('ACCESS_PATH_AVAILABLE')?'#78f3b4':'#ffd078',4,'center');
  if(path.length){const y=149,x0=341,span=124/(Math.max(1,path.length-1));path.forEach((room,i)=>{const x=x0+i*span; if(i)line({x:x-span,y},{x,y},'#78f3b488',1);X.fillStyle='#78f3b4';X.fillRect(Math.round(x-2),y-2,4,4)})}
  X.restore();
}
function renderDamageTopologyPanel(){
  const row=activeTopology();
  if(!row){$('damageTopology').innerHTML='<div class="mini">This layer composes the existing ship interface graph, room graph, system room bindings and maintenance interactions. It does not invent component hardware.</div>';return}
  if(row.status!=='TOPOLOGY_VIEW_AVAILABLE'){
    $('damageTopology').innerHTML=`<div class="topologyTitle">${escHtml(row.source_failure_id)}</div><span class="tag hold">${escHtml(row.status)}</span><div class="topologyWarn">${escHtml(row.truth_boundary||'Topology unavailable.')}</div>`;return
  }
  const access=row.access||{},maint=row.maintenance||{},preferred=access.preferred_room_path;
  const path=preferred?.rooms?.map(v=>escHtml(v)).join(' → ')||'NO PINNED ROOM PATH';
  const time=preferred?.travel_minutes==null?'UNKNOWN':`${preferred.travel_minutes} min`;
  const edges=(row.direct_interfaces||[]).slice(0,6).map(e=>`<div class="topologyEdge"><span>${escHtml(e.direction)}</span><b>${escHtml(e.neighbor_system_id)}</b><small>${escHtml(e.interface_type)} · interface only</small></div>`).join('')||'<div class="mini">No direct interfaces declared.</div>';
  const unresolved=(access.unresolved_or_external_bindings||[]).map(v=>`<code>${escHtml(v)}</code>`).join(' · ')||'none';
  $('damageTopology').innerHTML=`<div class="topologyTitle" style="color:${topologyColor(row)}">${escHtml(row.source_failure_id)}</div>
    <div class="topologyMeta"><span class="tag info">${escHtml(row.source_system_id)}</span><span class="tag hold">${escHtml(row.component_specificity?.status||'SYSTEM_LEVEL_ONLY')}</span></div>
    <div class="topologyAccess"><b>Repair-access route</b><span>${path}</span><small>${escHtml(access.status||'UNKNOWN')} · travel ${escHtml(time)}</small></div>
    <div class="topologyEdges"><b>Direct interfaces</b>${edges}</div>
    <div class="topologyMaintenance"><b>Maintenance boundary</b><span>maintenance system: ${maint.maintenance_system_present?'present':'not found'} · duration estimator: ${maint.repair_duration_estimator_present?'present':'not found'}</span><span>component spares: ${escHtml(maint.component_specific_spares_status||'UNKNOWN')}</span><span>unresolved/external bindings: ${unresolved}</span></div>
    <div class="topologyWarn">Direct neighbors are NOT automatically failed. Route display does NOT authorize access, consume spares, fabricate a repair part, execute a repair, clear the fault, or verify the outcome.</div>`;
}
function extendDamageTopologyRuntime(){
  const runtime=window.__axmLowPixelBridge;if(!runtime)return;
  const row=activeTopology(),access=row?.access||{},preferred=access.preferred_room_path||null;
  Object.assign(runtime,{
    damageTopologyVersion:'0.6.0-candidate',
    damageTopologyCount:DAMAGE_TOPOLOGY.topology_count??topologyRows().length,
    damageTopologyId:row?.topology_id||null,
    damageTopologySystemId:row?.source_system_id||null,
    damageTopologyAccessStatus:access.status||null,
    damageTopologyPreferredRoomPath:preferred?.rooms||[],
    damageTopologyTravelMinutes:preferred?.travel_minutes??null,
    damageTopologyDirectInterfaceCount:Array.isArray(row?.direct_interfaces)?row.direct_interfaces.length:0,
    damageTopologyComponentSpecificity:row?.component_specificity?.status||null,
    damageTopologyAuthority:'derived_review_only',
    mayExecuteRepair:false,
    mayConsumeSpares:false,
    mayFabricateRepairPart:false,
    mayClaimNeighborFailed:false,
    mayClearFault:false,
    repairVerified:false
  });
}
ensureTopologyPanel();
const drawV05Topology=draw;
draw=function(){drawV05Topology();drawDamageTopologyOverlay();renderDamageTopologyPanel();extendDamageTopologyRuntime()}
window.__axmLowPixelBridgeControl.activeDamageTopology=activeTopology;
draw();
