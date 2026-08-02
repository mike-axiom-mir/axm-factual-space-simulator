from __future__ import annotations
import json, shutil
from pathlib import Path
from axm_star_sim.ship_blueprint import create_ship_state, advance_ship_state, apply_encounter_effects, apply_failure_mode, state_hash, validate_blueprint, verify_ship_state
from axm_star_sim.crew_station_metrics import create_competency_state, record_competency_evidence, create_telemetry_snapshot, create_all_station_views, compute_learning_pressure, verify_competency_state
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'output/crew_station_metric_demo'; OUT.mkdir(parents=True,exist_ok=True)
initial=create_ship_state('AXM-V014-CREW-STATION-DEMO')
state=advance_ship_state(initial,55,activity_loads_kw={'external_sensors':9,'science_payload_and_analysis':8,'robotics_and_probe_operations':5},solar_flux_ratio=.72,data_generated_gb=28)
state=apply_encounter_effects(state,{'encounter_id':'AMBIGUOUS-THERMAL-RADIO-001','summary':'Unresolved close object with heat, interference and uncertain geometry.','observations':['two optical tracks disagree slightly','radio noise rises','no verified intent-bearing pattern'],'declared_intent':'unknown','effects':{'external_thermal_load_kw':8,'electromagnetic_interference_fraction':.35,'navigation_uncertainty_km_delta':6,'data_integrity_risk_fraction':.12}})
state=apply_failure_mode(state,'navigation_sensor_disagreement'); state=apply_failure_mode(state,'radiator_capacity_loss')
state['crew']['current_workload_by_role'].update({'mission_commander':.82,'vehicle_systems_engineer':.91,'flight_dynamics_navigation':.86}); state['state_hash']=state_hash(state)
comp=create_competency_state(); comp=record_competency_evidence(comp,role_id='vehicle_systems_engineer',skill_id='eng.power_energy',evidence_type='knowledge_check',outcome='passed',ship_state_hash=state['state_hash'])
roles=['mission_commander','ai_systems_integrator','flight_dynamics_navigation','vehicle_systems_engineer','science_anomaly_specialist','communications_data_robotics','crew_medical_officer']
report={'schema':'axm.crew-station-metric-demo.v1','blueprint_validation':validate_blueprint(),'ship_state_verification':verify_ship_state(state),'competency_verification':verify_competency_state(comp),'initial_ship_state':initial,'current_ship_state':state,'telemetry_snapshot':create_telemetry_snapshot(state,initial),'station_views':create_all_station_views(state,initial),'learning_pressure':{r:compute_learning_pressure(state,r,comp,initial) for r in roles},'competency_state':comp}
for name,value in [('demo_report.json',report),('ship_state.json',state),('competency_state.json',comp)]: (OUT/name).write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'valid':report['ship_state_verification']['valid'],'metrics':len(report['telemetry_snapshot']['cards']),'stations':len(report['station_views']['views'])},indent=2))


# Restore the canonical visual entry page after deterministic data rebuild.
_template = ROOT / "assets" / "demo_templates" / "crew_station_console.html"
(OUT / "crew_station_console.html").write_text(_template.read_text(encoding="utf-8"), encoding="utf-8")
