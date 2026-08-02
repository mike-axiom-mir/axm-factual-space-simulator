from __future__ import annotations
import copy, hashlib, json, math
from pathlib import Path
from typing import Any
from .ship_blueprint import evaluate_ship, load_blueprint, state_hash
PACKAGE_ROOT=Path(__file__).resolve().parents[2]; DATA_DIR=PACKAGE_ROOT/'data'
class CrewStationError(ValueError): pass

def canonical_json(v): return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def domain_hash(v,d): return hashlib.sha256(f"{d}|{canonical_json(v)}".encode()).hexdigest()
def _load(n): return json.loads((DATA_DIR/n).read_text(encoding="utf-8"))
def load_metric_registry(): return _load('ship_telemetry_metric_registry.json')
def load_display_registry(): return _load('crew_station_display_registry.json')
def load_competency_registry(): return _load('crew_competency_evolution_registry.json')
def metric_index(): return {x['id']:x for x in load_metric_registry()['metrics']}
def station_index(): return {x['id']:x for x in load_display_registry()['stations']}
def skill_index(): return {x['id']:x for x in load_competency_registry()['skills']}
def _safe_div(a,b): return None if b==0 else a/b
def _ttl(remaining,rate): return None if rate<=0 else max(0.0,remaining/rate)
def _latest_intent(s): return 'none_recorded' if not s['encounter_ledger'] else s['encounter_ledger'][-1].get('intent_assessment','unknown')
def _collision_quality(s):
    if not s['encounter_ledger']: return 'no_active_geometry'
    return 'sufficient' if len(s['encounter_ledger'][-1].get('observations',[]))>=2 and s['navigation']['navigation_uncertainty_km']<=5 else 'insufficient'

def extract_metric_values(s):
    e=evaluate_ship(s); p=e['power']; t=e['thermal']; l=e['life_support']; c=e['communications']; v=s['navigation']['velocity_km_s']
    soc=_safe_div(s['power']['battery_energy_kwh'],s['power']['battery_capacity_kwh']); deficit=max(0.0,-p['power_margin_kw'])
    bttl=_ttl(max(0.0,s['power']['battery_energy_kwh']-p['battery_reserve_energy_kwh']),deficit)
    httl=_ttl(max(0.0,t['thermal_storage_limit_kwh']-t['thermal_storage_kwh']),max(0.0,-t['thermal_margin_kw']))
    pttl=_ttl(max(0.0,l['cabin_pressure_kpa']-55.0),max(0.0,l['pressure_loss_rate_kpa_per_hour']))
    pb=next(x for x in load_blueprint(s['blueprint_id'])['systems'] if x['id']=='main_propulsion')
    maneuver=all(pb['parameters'][k]['value'] is not None for k in ('maximum_thrust_n','specific_impulse_s','propellant_mass_kg')) and load_blueprint(s['blueprint_id'])['design_points']['integrated_wet_mass_kg']['value'] is not None
    integrity=s.get('state_hash')==state_hash(s); visibility=float(s['communications']['telemetry_visibility_fraction'])
    command_integrity='trusted' if integrity and visibility>=.85 and not any(x.get('reason')=='data_integrity_risk' for x in s['command']['held_irreversible_actions']) else 'restricted'
    raw=bool(next(x for x in load_blueprint(s['blueprint_id'])['systems'] if x['id']=='external_sensors')['parameters']['raw_data_preservation']['value'])
    return {
    'ship_mode':s['mode'],'crew_survival_supported':e['crew_survival_state_currently_supported'],'minimum_critical_health':e['minimum_critical_system_health'],'active_fault_count':sum(len(x['active_fault_ids']) for x in s['system_health'].values()),'pending_command_recall':s['command']['pending_recall'] is not None,'held_irreversible_action_count':len(s['command']['held_irreversible_actions']),'mission_elapsed_minutes':s['mission_elapsed_minutes'],'state_integrity':integrity,
    'generated_power_kw':p['generated_power_kw'],'served_load_kw':p['served_load_kw'],'power_margin_kw':p['power_margin_kw'],'battery_energy_kwh':p['battery_energy_kwh'],'battery_soc_pct':None if soc is None else soc*100,'battery_reserve_pct':s['power']['battery_minimum_reserve_fraction']*100,'time_to_battery_reserve_h':bttl,'generation_availability_pct':s['power']['source_availability_fraction']*s['system_health']['electrical_power_generation']['availability']*100,'solar_flux_ratio':s['power']['solar_flux_ratio'],'shed_load_count':len(s['power']['shed_loads']),
    'waste_heat_kw':t['waste_heat_kw'],'thermal_rejection_kw':t['rejection_capacity_kw'],'thermal_margin_kw':t['thermal_margin_kw'],'thermal_storage_kwh':t['thermal_storage_kwh'],'thermal_storage_pct':100*t['thermal_storage_kwh']/t['thermal_storage_limit_kwh'] if t['thermal_storage_limit_kwh'] else None,'time_to_thermal_limit_h':httl,
    'cabin_pressure_kpa':l['cabin_pressure_kpa'],'pressure_loss_rate':l['pressure_loss_rate_kpa_per_hour'],'time_to_min_pressure_h':pttl,'co2_margin':l['co2_removal_margin_person_equivalent'],'water_recovery_pct':l['effective_water_recovery_fraction']*100,'water_days':l['estimated_water_days'],'oxygen_days':l['stored_oxygen_days_at_current_crew'],'active_humans':l['active_humans'],'air_quality_state':l['air_quality_state'],'water_quality_state':l['water_quality_state'],'stored_water_kg':s['water']['stored_potable_water_kg'],'net_water_loss_kg_day':l['net_water_loss_kg_per_day'],'available_human_crew':s['crew']['available_human_crew'],
    'position_x_km':s['navigation']['position_km'][0],'position_y_km':s['navigation']['position_km'][1],'position_z_km':s['navigation']['position_km'][2],'speed_km_s':math.sqrt(sum(x*x for x in v)),'navigation_uncertainty_km':s['navigation']['navigation_uncertainty_km'],'attitude_error_deg':s['navigation']['attitude_error_deg'],'pointing_performance_pct':s['navigation']['pointing_performance_multiplier']*100,'propulsion_available':s['navigation']['propulsion_available'],'maneuver_performance_known':maneuver,'collision_geometry_quality':_collision_quality(s),
    'communications_distance_m':c['distance_m'],'one_way_light_time_s':c['one_way_light_time_s'],'round_trip_light_time_s':c['round_trip_light_time_s'],'communications_availability_pct':c['availability']*100,'data_queue_gb':c['data_queue_gb'],'data_queue_pct':100*c['data_queue_gb']/s['communications']['store_capacity_gb'] if s['communications']['store_capacity_gb'] else None,'telemetry_visibility_pct':visibility*100,'command_integrity_state':command_integrity,
    'structure_health_pct':s['structure']['health']*100,'pressure_boundary_state':s['structure']['pressure_boundary_state'],'isolated_room_count':len(s['structure']['isolated_rooms']),'radiation_environment_index':s['radiation']['environment_index'],'cumulative_radiation_exposure':s['radiation']['cumulative_relative_exposure'],'shelter_active':s['radiation']['shelter_active'],'external_heat_kw':s['thermal']['extra_external_heat_kw'],'mmod_health_pct':s['system_health']['mmod_and_external_protection']['health']*100,
    'sensor_health_pct':s['system_health']['external_sensors']['health']*100,'sensor_availability_pct':s['system_health']['external_sensors']['availability']*100,'sensor_mode':s['system_health']['external_sensors']['mode'],'encounter_count':len(s['encounter_ledger']),'latest_intent_assessment':_latest_intent(s),'raw_data_preserved':raw,'robotics_health_pct':s['system_health']['robotics_and_probe_operations']['health']*100,'robotics_availability_pct':s['system_health']['robotics_and_probe_operations']['availability']*100,
    'open_work_order_count':len(s['maintenance']['open_work_orders']),'spares_index':s['maintenance']['spares_index'],'repair_capacity':s['maintenance']['repair_capacity_person_hours_per_day'],'workload_commander':s['crew']['current_workload_by_role'].get('mission_commander',0),'workload_engineering':s['crew']['current_workload_by_role'].get('vehicle_systems_engineer',0),'workload_science':s['crew']['current_workload_by_role'].get('science_anomaly_specialist',0),'workload_navigation':s['crew']['current_workload_by_role'].get('flight_dynamics_navigation',0)}

def _match(v,c):
    if c is None or v is None: return False
    op,t=c['op'],c.get('value')
    if op=='lt': return float(v)<float(t)
    if op=='gt': return float(v)>float(t)
    if op=='eq': return v==t
    if op=='neq': return v!=t
    raise CrewStationError('unknown condition')
def _status(m,v):
    if v is None:return 'unavailable'
    for st in ('emergency','warning','caution'):
        if _match(v,m['limits'].get(st)):return st
    return 'normal'
def _quality(m,s):
    vals=[]
    for sid in m['quality_source_system_ids']:
        x=s['system_health'].get(sid)
        if x: vals.append(min(float(x['health']),float(x['availability'])))
    q=min(vals) if vals else 1.0
    if m['system_id'] in {'communications','avionics_cdh'}: q=min(q,float(s['communications']['telemetry_visibility_fraction']))
    label='unreliable' if q<.25 else 'degraded' if q<.6 else 'usable_with_caution' if q<.85 else 'valid'
    return {'state':label,'quality_fraction':round(q,6),'freshness':'current_onboard_snapshot','expected_update_period_s':m['expected_update_period_s']}
def _trend(v,p):
    if v is None or p is None:return 'unknown'
    if isinstance(v,(bool,str)):return 'changed' if v!=p else 'steady'
    d=float(v)-float(p); tol=max(1e-9,abs(float(p))*1e-4)
    return 'rising' if d>tol else 'falling' if d<-tol else 'steady'

def create_telemetry_snapshot(s,previous_state=None):
    vals=extract_metric_values(s); prev=extract_metric_values(previous_state) if previous_state else {}; cards=[]
    for m in load_metric_registry()['metrics']:
        v=vals.get(m['extractor']); card={'metric_id':m['id'],'display_name':m['display_name'],'system_id':m['system_id'],'value':v,'unit':m['unit'],'truth_type':m['truth_type'],'status':_status(m,v),'trend':_trend(v,prev.get(m['extractor'])),'quality':_quality(m,s),'meaning':m['meaning'],'plain_language':m['plain_language'],'role_ids':m['role_ids'],'commander_visible':m['commander_visible'],'display_priority':m['display_priority'],'control_influence_ids':m['control_influence_ids'],'limits':m['limits']};card['card_receipt']=domain_hash(card,'AXM-TELEMETRY-CARD-V1');cards.append(card)
    out={'schema':'axm.ship-telemetry-snapshot.v1','blueprint_id':s['blueprint_id'],'blueprint_commitment':s['blueprint_commitment'],'ship_state_hash':s['state_hash'],'mission_elapsed_minutes':s['mission_elapsed_minutes'],'cards':cards};out['snapshot_receipt']=domain_hash(out,'AXM-TELEMETRY-SNAPSHOT-V1');return out

def derive_alert_queue(s,snapshot):
    alerts=[]
    for c in snapshot['cards']:
        if c['status'] not in {'caution','warning','emergency'}:continue
        a={'priority':c['status'],'event_id':'METRIC:'+c['metric_id'],'name':c['display_name'],'timestamp':s['mission_elapsed_minutes'],'system_id':c['system_id'],'module_or_element':'crew_display','active_state':True,'acknowledge_state':'unacknowledged','data_quality':c['quality']['state'],'root_cause_if_known':None,'procedure_link_if_available':None,'metric_value':c['value'],'unit':c['unit'],'plain_language':c['plain_language']};a['alert_receipt']=domain_hash(a,'AXM-CREW-ALERT-V1');alerts.append(a)
    for f in s['fault_ledger']:
        pr='emergency' if f['criticality']=='crew_survival' else 'warning' if f['criticality']=='high' else 'caution';a={'priority':pr,'event_id':f['failure_mode_id'],'name':f['failure_mode_id'].replace('_',' ').title(),'timestamp':f['mission_elapsed_minutes'],'system_id':f['system_id'],'module_or_element':'registered_failure_mode','active_state':f['failure_mode_id'] in s['system_health'][f['system_id']]['active_fault_ids'],'acknowledge_state':'unacknowledged','data_quality':'registered_fault','root_cause_if_known':f['failure_mode_id'],'procedure_link_if_available':f['automatic_response']};a['alert_receipt']=domain_hash(a,'AXM-CREW-ALERT-V1');alerts.append(a)
    order={'emergency':0,'warning':1,'caution':2,'advisory':3};alerts.sort(key=lambda x:(order[x['priority']],-float(x['timestamp']),x['event_id']));return alerts

def create_station_view(s,station_id,previous_state=None):
    stations=station_index()
    if station_id not in stations:raise CrewStationError('unknown station')
    st=copy.deepcopy(stations[station_id]);snap=create_telemetry_snapshot(s,previous_state);cards={x['metric_id']:x for x in snap['cards']};surfaces=[]
    for sf in st['display_surfaces']:
        cs=[cards[mid] for mid in sf['metric_ids']];surfaces.append({**sf,'metric_cards':cs,'abnormal_count':sum(x['status']!='normal' for x in cs)})
    controls=[x for x in load_display_registry()['control_influences'] if x['id'] in st['control_influence_ids']]
    out={'schema':'axm.crew-station-view.v1','station_id':station_id,'display_name':st['display_name'],'ship_state_hash':s['state_hash'],'blueprint_commitment':s['blueprint_commitment'],'mode':s['mode'],'seat_role_ids':st['seat_role_ids'],'surfaces':surfaces,'alert_queue':derive_alert_queue(s,snap),'controls':controls,'display_rules':load_display_registry()['display_rules']};out['station_view_receipt']=domain_hash(out,'AXM-CREW-STATION-VIEW-V1');return out

def create_all_station_views(s,previous_state=None):
    views={sid:create_station_view(s,sid,previous_state) for sid in station_index()};out={'schema':'axm.all-crew-station-views.v1','ship_state_hash':s['state_hash'],'blueprint_commitment':s['blueprint_commitment'],'views':views};out['views_receipt']=domain_hash(out,'AXM-ALL-STATION-VIEWS-V1');return out

def create_competency_state():
    state={'schema':'axm.crew-competency-state.v1','levels':{x['id']:{'level':0,'evidence_ids':[],'last_assessment':None} for x in load_competency_registry()['skills']},'evidence_ledger':[],'promotion_ledger':[]};state['state_hash']=competency_state_hash(state);return state
def competency_state_hash(s):
    c=copy.deepcopy(s);c.pop('state_hash',None);return domain_hash(c,'AXM-CREW-COMPETENCY-STATE-V1')
def record_competency_evidence(cs,*,role_id,skill_id,evidence_type,outcome,ship_state_hash,verifier_id=None,notes=''):
    skills=skill_index()
    if skill_id not in skills:raise CrewStationError('unknown skill')
    sk=skills[skill_id]
    if role_id!=sk['role_id']:raise CrewStationError('evidence role does not own skill')
    if evidence_type not in sk['accepted_evidence_types']:raise CrewStationError('evidence type not accepted')
    if outcome not in {'passed','failed','observed','incomplete'}:raise CrewStationError('invalid outcome')
    u=copy.deepcopy(cs);prev=u['evidence_ledger'][-1]['evidence_hash'] if u['evidence_ledger'] else None;r={'sequence':len(u['evidence_ledger'])+1,'role_id':role_id,'skill_id':skill_id,'evidence_type':evidence_type,'outcome':outcome,'ship_state_hash':ship_state_hash,'verifier_id':verifier_id,'notes':notes,'previous_evidence_hash':prev};r['evidence_id']=domain_hash(r,'AXM-COMPETENCY-EVIDENCE-ID-V1')[:24];r['evidence_hash']=domain_hash(r,'AXM-COMPETENCY-EVIDENCE-V1');u['evidence_ledger'].append(r);u['levels'][skill_id]['evidence_ids'].append(r['evidence_id']);u['state_hash']=competency_state_hash(u);return u
def _passed(cs,sid):return [x for x in cs['evidence_ledger'] if x['skill_id']==sid and x['outcome']=='passed']
def assess_skill_promotion(cs,skill_id,target_level):
    sk=skill_index().get(skill_id)
    if not sk:raise CrewStationError('unknown skill')
    cur=int(cs['levels'][skill_id]['level'])
    if target_level!=cur+1:return {'skill_id':skill_id,'current_level':cur,'target_level':target_level,'eligible':False,'missing':['promotion_must_be_one_level_at_a_time']}
    required=set(sk['required_evidence_by_promotion'][str(target_level)]);records=_passed(cs,skill_id);present={x['evidence_type'] for x in records};missing=sorted(required-present)
    if 'verifier_signoff' in required and not any(x['evidence_type']=='verifier_signoff' and x.get('verifier_id') for x in records):missing.append('verifier_identity')
    out={'schema':'axm.skill-promotion-assessment.v1','skill_id':skill_id,'current_level':cur,'target_level':target_level,'eligible':not missing,'required_evidence':sorted(required),'present_evidence':sorted(present),'missing':sorted(set(missing))};out['assessment_receipt']=domain_hash(out,'AXM-SKILL-PROMOTION-ASSESSMENT-V1');return out
def promote_skill(cs,skill_id,target_level):
    a=assess_skill_promotion(cs,skill_id,target_level)
    if not a['eligible']:raise CrewStationError('promotion evidence incomplete: '+str(a['missing']))
    u=copy.deepcopy(cs);u['levels'][skill_id]['level']=target_level;u['levels'][skill_id]['last_assessment']=a['assessment_receipt'];prev=u['promotion_ledger'][-1]['promotion_hash'] if u['promotion_ledger'] else None;r={'sequence':len(u['promotion_ledger'])+1,'skill_id':skill_id,'target_level':target_level,'assessment_receipt':a['assessment_receipt'],'previous_promotion_hash':prev};r['promotion_hash']=domain_hash(r,'AXM-COMPETENCY-PROMOTION-V1');u['promotion_ledger'].append(r);u['state_hash']=competency_state_hash(u);return u

def compute_learning_pressure(s,role_id,competency_state=None,previous_state=None):
    cards={x['metric_id']:x for x in create_telemetry_snapshot(s,previous_state)['cards']};cs=competency_state or create_competency_state();f=load_competency_registry()['learning_pressure_factors'];rows=[]
    for sk in load_competency_registry()['skills']:
        if sk['role_id']!=role_id:continue
        mc=[cards[x] for x in sk['metric_ids'] if x in cards];ab=sum(1 if x['status'] in {'warning','emergency'} else .6 if x['status']=='caution' else .2 if x['quality']['state']!='valid' else 0 for x in mc)/max(1,len(mc));faults=sum(1 for sid in sk['system_ids'] for _ in s['system_health'].get(sid,{}).get('active_fault_ids',[]));ff=min(1,faults/2);lvl=int(cs['levels'][sk['id']]['level']);gap=(sk['maximum_level']-lvl)/sk['maximum_level'];control=.35 if s['command']['pending_recall'] else .1;score=f['metric_alert_exposure']*ab+f['role_responsibility']+f['active_fault_in_related_system']*ff+f['command_or_control_use']*control+f['qualification_gap']*gap
        rows.append({'skill_id':sk['id'],'display_name':sk['display_name'],'current_level':lvl,'learning_pressure':round(min(1,score),6),'abnormal_metric_ids':[x['metric_id'] for x in mc if x['status']!='normal'],'related_active_fault_count':faults,'next_promotion_assessment':assess_skill_promotion(cs,sk['id'],lvl+1) if lvl<sk['maximum_level'] else None,'interpretation':'Operational learning demand inferred from responsibility, non-nominal metrics, faults and qualification gaps. It is not a claim about personality or desire.'})
    rows.sort(key=lambda x:(-x['learning_pressure'],x['skill_id']));out={'schema':'axm.role-learning-pressure.v1','role_id':role_id,'ship_state_hash':s['state_hash'],'ranked_skills':rows,'highest_pressure_skill_id':rows[0]['skill_id'] if rows else None};out['pressure_receipt']=domain_hash(out,'AXM-ROLE-LEARNING-PRESSURE-V1');return out

def verify_competency_state(s):
    failures=[];prev=None
    for i,r in enumerate(s.get('evidence_ledger',[]),1):
        c=copy.deepcopy(r);sup=c.pop('evidence_hash',None)
        if c.get('sequence')!=i:failures.append(f'evidence sequence mismatch at {i}')
        if c.get('previous_evidence_hash')!=prev:failures.append(f'evidence previous hash mismatch at {i}')
        if sup!=domain_hash(c,'AXM-COMPETENCY-EVIDENCE-V1'):failures.append(f'evidence hash mismatch at {i}')
        prev=sup
    prev=None
    for i,r in enumerate(s.get('promotion_ledger',[]),1):
        c=copy.deepcopy(r);sup=c.pop('promotion_hash',None)
        if c.get('sequence')!=i:failures.append(f'promotion sequence mismatch at {i}')
        if c.get('previous_promotion_hash')!=prev:failures.append(f'promotion previous hash mismatch at {i}')
        if sup!=domain_hash(c,'AXM-COMPETENCY-PROMOTION-V1'):failures.append(f'promotion hash mismatch at {i}')
        prev=sup
    if s.get('state_hash')!=competency_state_hash(s):failures.append('competency state hash mismatch')
    out={'schema':'axm.crew-competency-state-verification.v1','valid':not failures,'failures':failures,'evidence_count':len(s.get('evidence_ledger',[])),'promotion_count':len(s.get('promotion_ledger',[]))};out['verification_receipt']=domain_hash(out,'AXM-COMPETENCY-VERIFY-V1');return out
