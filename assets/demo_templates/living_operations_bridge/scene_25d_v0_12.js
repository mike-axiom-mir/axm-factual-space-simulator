/* v0.12 whole-simulator low-graphic 3D / 2.5D presentation shell */
const LOW_GRAPHIC_3D=STORY.low_graphic_3d_scene||{rooms:[],room_edges:[],station_anchors:[],rehearsal_routes:[],room_count:0};
let scene25dMode='director';
function scene25dRooms(){return Array.isArray(LOW_GRAPHIC_3D.rooms)?LOW_GRAPHIC_3D.rooms:[]}
function scene25dRoom(id){return scene25dRooms().find(row=>row.room_id===id)||null}
function scene25dRoutes(){return Array.isArray(LOW_GRAPHIC_3D.rehearsal_routes)?LOW_GRAPHIC_3D.rehearsal_routes:[]}
function activeScene25dRoute(){const p=typeof activeProcedure==='function'?activeProcedure():null;if(!p)return null;return scene25dRoutes().find(row=>row.source_failure_id===p.source_failure_id)||null}
function scene25dFocusRoom(){
  const route=activeScene25dRoute();if(route?.target_room_id&&scene25dRoom(route.target_room_id))return route.target_room_id;
  const focus=typeof operationalFocus==='function'?operationalFocus():'command';
  const map={engineering:'engineering',science:'research_strategy',navigation:'command_deck',command:'command_deck'};
  if(scene25dRoom(map[focus]))return map[focus];
  const rooms=scene25dRooms();if(!rooms.length)return null;
  return rooms[Math.floor((reduced?cueIndex:t/5)%rooms.length)]?.room_id||rooms[0].room_id;
}
function effectiveScene25dMode(){
  if(scene25dMode!=='director')return scene25dMode;
  if(activeScene25dRoute())return'interior_follow';
  const seg=typeof phase==='function'?phase()[0]:'command_outbound';
  if(seg==='observation_window')return'exterior_orbit';
  if(seg==='telemetry_return'&&Math.floor((reduced?cueIndex:t)/4)%2)return'interior_follow';
  return'ship_cutaway';
}
function setScene25dMode(value){
  const allowed=['director','legacy_bridge','ship_cutaway','interior_follow','exterior_orbit'];
  scene25dMode=allowed.includes(value)?value:'director';
  if($('scene25d'))$('scene25d').value=scene25dMode;
  draw();return scene25dMode;
}
function isoPoint(room,scale=1,ox=W/2,oy=55){
  const p=room?.presentation_position||{};const gx=Number(p.x)||0,gy=Number(p.y)||0,gz=Number(p.z)||0;
  return{x:ox+(gx-gy*.42)*48*scale,y:oy+(gy+gx*.18)*30*scale-gz*18*scale};
}
function roomSceneColor(room,focus=false,drill=false){
  if(drill)return'#6a252d';if(focus)return'#16445a';
  const type=String(room?.room_type||'');
  if(type==='technical')return'#16394a';if(type==='analysis')return'#293653';if(type.startsWith('personal'))return'#342a45';if(type==='crew_life')return'#314332';if(type==='transit')return'#26313a';return'#203646';
}
function drawIsoRoom(room,{focus=false,drill=false,scale=1,ox=W/2,oy=55}={}){
  const p=isoPoint(room,scale,ox,oy),rw=54*scale,rh=23*scale,depth=10*scale;
  const pulse=reduced?.55:.42+.35*Math.sin(t*1.15+(hashSeed(room.room_id)%17));
  const body=roomSceneColor(room,focus,drill),edge=drill?'#ff736f':focus?'#63e8ff':'#416174';
  poly([{x:p.x-rw/2,y:p.y},{x:p.x,y:p.y-rh/2},{x:p.x+rw/2,y:p.y},{x:p.x,y:p.y+rh/2}],body,edge);
  poly([{x:p.x-rw/2,y:p.y},{x:p.x,y:p.y+rh/2},{x:p.x,y:p.y+rh/2+depth},{x:p.x-rw/2,y:p.y+depth}],'#101a22',edge);
  poly([{x:p.x+rw/2,y:p.y},{x:p.x,y:p.y+rh/2},{x:p.x,y:p.y+rh/2+depth},{x:p.x+rw/2,y:p.y+depth}],'#0b141b',edge);
  const systems=Array.isArray(room.ship_system_bindings)?room.ship_system_bindings:[];
  for(let i=0;i<Math.min(7,systems.length);i++){const on=reduced?i%2===0:((activityTick()+i+hashSeed(room.room_id))%4!==0);X.fillStyle=on?(drill?'#ff736f':focus?'#63e8ff':'#78f3b4'):'#1b3039';X.fillRect(Math.round(p.x-rw*.34+i*6*scale),Math.round(p.y+rh*.13),Math.max(1,Math.round(3*scale)),Math.max(1,Math.round(2*scale)))}
  if(!reduced&&pulse>.63){X.globalAlpha=.13;X.fillStyle=drill?'#ff736f':focus?'#63e8ff':'#78f3b4';X.fillRect(Math.round(p.x-rw/2),Math.round(p.y-rh/2),Math.round(rw),Math.round(rh));X.globalAlpha=1}
  text(String(room.display_name||room.room_id).toUpperCase().slice(0,22),p.x,p.y+rh/2+depth+7,focus?'#dff8ff':'#7897a6',5,'center');
  return p;
}
function drawScene25dBackground(label){
  X.fillStyle='#02050a';X.fillRect(0,0,W,H);
  for(let y=18;y<210;y+=12){X.strokeStyle='#0a1720';X.beginPath();X.moveTo(0,y);X.lineTo(W,y);X.stroke()}
  for(let x=0;x<W;x+=16){X.strokeStyle='#07131a';X.beginPath();X.moveTo(x,0);X.lineTo(x,220);X.stroke()}
  text(label,12,24,'#63e8ff',7);text('2.5D PRESENTATION GEOMETRY · NOT PHYSICAL DIMENSIONS',468,24,'#5f7b88',5,'right');
}
function drawSceneEdges(roomPoints){
  const edges=Array.isArray(LOW_GRAPHIC_3D.room_edges)?LOW_GRAPHIC_3D.room_edges:[];
  for(const edge of edges){const a=roomPoints[edge.from_room_id],b=roomPoints[edge.to_room_id];if(!a||!b)continue;line({x:a.x,y:a.y+8},{x:b.x,y:b.y+8},'#244a59',2)}
}
function drawStationMarkers(roomPoints){
  const anchors=Array.isArray(LOW_GRAPHIC_3D.station_anchors)?LOW_GRAPHIC_3D.station_anchors:[];
  const counts={};
  for(const a of anchors){const p=roomPoints[a.room_id];if(!p)continue;const n=counts[a.room_id]||0;counts[a.room_id]=n+1;const angle=(n*.9)+(reduced?0:t*.22);const x=p.x-12+n*7+Math.sin(angle)*2,y=p.y-7-Math.cos(angle)*1.5;X.fillStyle=a.station_id==='engineering_station'?'#ffd078':a.station_id==='science_station'?'#b9a5ff':'#63e8ff';X.fillRect(Math.round(x-2),Math.round(y-5),4,6);X.fillStyle='#d1a06f';X.fillRect(Math.round(x-2),Math.round(y-8),4,3)}
}
function routeProgressPoint(route,roomPoints){
  const ids=Array.isArray(route?.route_rooms)?route.route_rooms:[];if(ids.length<2)return ids.length?roomPoints[ids[0]]:null;
  const p=reduced?.65:((t*.22)%1),segments=ids.length-1,raw=p*segments,index=Math.min(segments-1,Math.floor(raw)),local=raw-index;
  const a=roomPoints[ids[index]],b=roomPoints[ids[index+1]];if(!a||!b)return null;
  return{x:a.x+(b.x-a.x)*local,y:a.y+(b.y-a.y)*local};
}
function drawRehearsalRoute(roomPoints){
  const route=activeScene25dRoute();if(!route)return;
  const ids=Array.isArray(route.route_rooms)?route.route_rooms:[];
  for(let i=1;i<ids.length;i++){const a=roomPoints[ids[i-1]],b=roomPoints[ids[i]];if(a&&b)line({x:a.x,y:a.y+7},{x:b.x,y:b.y+7},'#ff9a70',2)}
  const walker=routeProgressPoint(route,roomPoints);if(walker){const bob=reduced?0:Math.sin(t*5)*2;X.fillStyle='#ffd078';X.fillRect(Math.round(walker.x-2),Math.round(walker.y-10+bob),5,7);X.fillStyle='#f1b978';X.fillRect(Math.round(walker.x-2),Math.round(walker.y-13+bob),5,3)}
  X.fillStyle='#17090ce8';X.fillRect(12,184,176,25);X.strokeStyle='#ff736f';X.strokeRect(12,184,176,25);text('PROCEDURE DRILL ROUTE · NOT LIVE CREW',18,193,'#ff9a70',5);text(`${route.source_failure_id} → ${route.target_room_id||'NO PINNED TARGET'}`,18,202,'#dff8ff',5);
}
function drawShipCutaway25d(){
  drawScene25dBackground('SHIP CUTAWAY · WHOLE INTERIOR GRAPH');
  const rooms=scene25dRooms(),focusId=scene25dFocusRoom(),route=activeScene25dRoute(),roomPoints={};
  for(const room of rooms)roomPoints[room.room_id]=isoPoint(room,.83,W/2,47);
  drawSceneEdges(roomPoints);
  for(const room of rooms){const drill=route?.target_room_id===room.room_id;roomPoints[room.room_id]=drawIsoRoom(room,{focus:room.room_id===focusId,drill,scale:.83,ox:W/2,oy:47})}
  drawStationMarkers(roomPoints);drawRehearsalRoute(roomPoints);
  const unresolved=Array.isArray(LOW_GRAPHIC_3D.unresolved_station_anchors)?LOW_GRAPHIC_3D.unresolved_station_anchors.length:0;
  X.fillStyle='#031018dc';X.fillRect(300,184,168,25);X.strokeStyle='#31586b';X.strokeRect(300,184,168,25);text(`${rooms.length} ROOMS · ${LOW_GRAPHIC_3D.station_count||0} PINNED STATIONS`,307,193,'#78f3b4',5);text(`${unresolved} STATION ROOM HOLDS · READ ONLY`,307,202,'#7f9aa8',5);
}
function focusedRoomForInterior(){const id=scene25dFocusRoom();return scene25dRoom(id)||scene25dRooms()[0]||null}
function drawInteriorFollow25d(){
  const room=focusedRoomForInterior();drawScene25dBackground('INTERIOR FOLLOW · ROOM ACTIVITY');if(!room){text('NO PINNED INTERIOR ROOMS',W/2,H/2,'#ffd078',8,'center');return}
  const p={x:W/2,y:92},rw=80,rh=36,depth=20,route=activeScene25dRoute(),drill=route?.target_room_id===room.room_id;
  poly([{x:p.x-rw,y:p.y},{x:p.x,y:p.y-rh},{x:p.x+rw,y:p.y},{x:p.x,y:p.y+rh}],roomSceneColor(room,true,drill),drill?'#ff736f':'#63e8ff');
  poly([{x:p.x-rw,y:p.y},{x:p.x,y:p.y+rh},{x:p.x,y:p.y+rh+depth},{x:p.x-rw,y:p.y+depth}],'#0d1920','#31586b');
  poly([{x:p.x+rw,y:p.y},{x:p.x,y:p.y+rh},{x:p.x,y:p.y+rh+depth},{x:p.x+rw,y:p.y+depth}],'#081117','#31586b');
  for(let i=-2;i<=2;i++){const x=p.x+i*25;X.fillStyle=(reduced||((activityTick()+i)%3))?'#63e8ff':'#17313c';X.fillRect(x-8,p.y-14+(i%2)*5,16,4)}
  const systems=Array.isArray(room.ship_system_bindings)?room.ship_system_bindings:[];
  systems.slice(0,8).forEach((system,i)=>{const x=127+(i%4)*76,y=155+Math.floor(i/4)*17;X.strokeStyle='#254b5c';X.strokeRect(x,y,68,12);X.fillStyle=reduced?'#78f3b4':(activityPulse(hashSeed(system)%11,1.2)>.42?'#78f3b4':'#244550');X.fillRect(x+4,y+4,4,4);text(String(system).replaceAll('_',' ').slice(0,10).toUpperCase(),x+12,y+8,'#a8c0ca',4)});
  const anchors=(LOW_GRAPHIC_3D.station_anchors||[]).filter(a=>a.room_id===room.room_id);anchors.slice(0,6).forEach((a,i)=>{const angle=(i/Math.max(1,anchors.length))*TAU+(reduced?0:t*.12),x=p.x+Math.cos(angle)*43,y=p.y+Math.sin(angle)*17;X.fillStyle='#2d5e8c';X.fillRect(Math.round(x-3),Math.round(y-7),6,8);X.fillStyle='#d5a06e';X.fillRect(Math.round(x-3),Math.round(y-10),6,3)});
  text(String(room.display_name||room.room_id).toUpperCase(),W/2,39,drill?'#ff9a70':'#dff8ff',8,'center');text(`${String(room.room_type||'unknown').toUpperCase()} · ${systems.length} SYSTEM BINDINGS`,W/2,49,'#7f9aa8',5,'center');
  const neighbors=(room.adjacent_rooms||[]).join(' · ')||'NONE';text(`ADJACENT: ${neighbors}`.toUpperCase().slice(0,76),W/2,207,'#7f9aa8',5,'center');
  if(drill){X.fillStyle='#18080cdf';X.fillRect(110,57,260,15);X.strokeStyle='#ff736f';X.strokeRect(110,57,260,15);text('DRILL TARGET ONLY · ACTIVE FAULT NOT CLAIMED',W/2,67,'#ff9a70',5,'center')}
}
function drawExterior25d(){
  drawStars();
  const q=cue(),cx=270+(reduced?0:Math.sin(t*.18)*9),cy=111+(reduced?0:Math.sin(t*.31)*3),scale=1.15;
  poly([{x:cx-76*scale,y:cy},{x:cx-30*scale,y:cy-17*scale},{x:cx+50*scale,y:cy-12*scale},{x:cx+85*scale,y:cy},{x:cx+50*scale,y:cy+12*scale},{x:cx-30*scale,y:cy+17*scale}],'#172b36','#55798a');
  poly([{x:cx-18*scale,y:cy-17*scale},{x:cx+31*scale,y:cy-35*scale},{x:cx+48*scale,y:cy-11*scale}],'#10232c','#416174');
  poly([{x:cx-18*scale,y:cy+17*scale},{x:cx+31*scale,y:cy+35*scale},{x:cx+48*scale,y:cy+11*scale}],'#10232c','#416174');
  X.fillStyle='#63e8ff';for(let i=0;i<5;i++)X.fillRect(Math.round(cx-38+i*16),Math.round(cy-5+(i%2)*7),7,2);
  const thrust=reduced?3:3+Math.floor(activityPulse(2,3.4)*8);X.fillStyle='#63e8ff';X.fillRect(Math.round(cx-84*scale-thrust),Math.round(cy-3),thrust,2);X.fillStyle='#b9a5ff';X.fillRect(Math.round(cx-84*scale-thrust*.7),Math.round(cy+2),Math.round(thrust*.7),1);
  const target={x:91,y:83},rr=35+(reduced?0:Math.sin(t*.24)*2);X.fillStyle='#142f3f';X.beginPath();X.arc(target.x,target.y,rr,0,TAU);X.fill();X.fillStyle='#3d765f';X.fillRect(target.x-19,target.y-3,32,4);X.fillRect(target.x-5,target.y+11,19,3);X.strokeStyle='#63e8ff55';X.strokeRect(target.x-rr-3,target.y-rr-3,(rr+3)*2,(rr+3)*2);
  const [seg,p]=phase(),from=seg==='telemetry_return'?target:{x:cx,y:cy},to=seg==='telemetry_return'?{x:cx,y:cy}:target,px=from.x+(to.x-from.x)*p,py=from.y+(to.y-from.y)*p;line(from,to,seg==='observation_window'?'#b9a5ff66':'#78f3b466',1);X.fillStyle=seg==='observation_window'?'#b9a5ff':'#78f3b4';X.fillRect(Math.round(px-2),Math.round(py-2),4,4);
  text('EXTERIOR REPLAY · PRESENTATION TRAJECTORY ONLY',12,24,'#63e8ff',7);text('NO EPHEMERIS / THRUST / VELOCITY CLAIM',468,24,'#5f7b88',5,'right');text(q.target_planet_name||'TARGET',target.x,target.y+rr+11,'#78f3b4',6,'center');text('FRONTIER SURVEY SHIP · LOW-GRAPHIC SILHOUETTE',cx,cy+54,'#9ab0b9',5,'center');
}
function drawScene25d(){
  const mode=effectiveScene25dMode();if(mode==='legacy_bridge')return;
  if(mode==='interior_follow')drawInteriorFollow25d();else if(mode==='exterior_orbit')drawExterior25d();else drawShipCutaway25d();
  X.fillStyle='#02070bd9';X.fillRect(8,219,464,18);X.strokeStyle='#254b5c';X.strokeRect(8,219,464,18);text(`SCENE ${mode.toUpperCase().replaceAll('_',' ')} · ANIMATION AUTHORITY ONLY`,15,228,'#dff8ff',5);text('WORLD WRITE / FAULT CLEAR / CREW MOVE / RESOURCE RESTORE: FORBIDDEN',465,228,'#ff9fac',4,'right');
}
function ensureScene25dPanel(){
  if($('scene25dPanel'))return;const anchor=$('runtime');if(!anchor)return;
  anchor.insertAdjacentHTML('afterend','<div id="scene25dPanel" class="scene25dPanel"><b>Whole-sim 2.5D shell</b><span>Room graph, crew markers, systems, rehearsal routes and exterior replay are animated from existing source data.</span><small>Presentation geometry only · no hidden simulation authority.</small></div>');
}
function renderScene25dPanel(){
  const panel=$('scene25dPanel');if(!panel)return;const mode=effectiveScene25dMode(),focus=scene25dFocusRoom(),route=activeScene25dRoute();
  panel.innerHTML=`<b>${escHtml(mode.replaceAll('_',' '))}</b><span>focus: ${escHtml(focus||'none')} · rooms ${LOW_GRAPHIC_3D.room_count??scene25dRooms().length}</span><small>${route?`drill route ${escHtml(route.source_failure_id)} · NOT active-fault truth`:'no procedure drill selected · ambient/source receipt animation only'}</small>`;
}
function extendScene25dRuntime(){
  const runtime=window.__axmLowPixelBridge;if(!runtime)return;const route=activeScene25dRoute();
  Object.assign(runtime,{lowGraphic3dVersion:'0.12.0-candidate',lowGraphic3dSceneHash:LOW_GRAPHIC_3D.scene_hash||null,lowGraphic3dSceneMode:scene25dMode,lowGraphic3dEffectiveMode:effectiveScene25dMode(),lowGraphic3dRoomCount:LOW_GRAPHIC_3D.room_count??scene25dRooms().length,lowGraphic3dFocusRoomId:scene25dFocusRoom(),lowGraphic3dRehearsalRouteFailureId:route?.source_failure_id||null,lowGraphic3dAuthority:'read_only_visual_projection',rendererMayAnimate:true,rendererMayMoveAuthoritativeCrew:false,rendererMayClaimFaultActiveFromRehearsal:false,rendererMayExecuteAction:false,rendererMayClearFault:false,rendererMayExitSafeState:false,rendererMayApplyOperationalRelease:false,rendererMayRestoreResources:false,rendererMayChangeTruthLabels:false});
}
ensureScene25dPanel();
const sceneSelect=$('scene25d');if(sceneSelect){sceneSelect.value=scene25dMode;sceneSelect.addEventListener('change',e=>setScene25dMode(e.target.value))}
const drawV11Scene25d=draw;
draw=function(){drawV11Scene25d();ensureScene25dPanel();drawScene25d();renderScene25dPanel();extendScene25dRuntime()}
window.__axmLowPixelBridgeControl.setScene25dMode=setScene25dMode;
window.__axmLowPixelBridgeControl.effectiveScene25dMode=effectiveScene25dMode;
window.__axmLowPixelBridgeControl.scene25dFocusRoom=scene25dFocusRoom;
draw();
