from __future__ import annotations
import json
from pathlib import Path
from axm_star_sim.ship_blueprint import create_ship_state, advance_ship_state, apply_failure_mode, verify_ship_state
from axm_star_sim.crew_station_metrics import create_telemetry_snapshot, create_all_station_views, compute_learning_pressure, create_competency_state
ROOT=Path(__file__).resolve().parents[1]; modes=['power_generation_degraded','radiator_capacity_loss','cabin_pressure_leak','navigation_sensor_disagreement','communications_pointing_loss','radiation_event']; failures=[]; cards=views=pressures=0
roles=['mission_commander','ai_systems_integrator','flight_dynamics_navigation','vehicle_systems_engineer','science_anomaly_specialist','communications_data_robotics','crew_medical_officer']
for i in range(300):
 base=create_ship_state(f'AXM-V014-STRESS-{i:04d}'); state=advance_ship_state(base,20+i%100,solar_flux_ratio=0 if i%23==0 else .55+(i%40)/100,data_generated_gb=float(i%25)); state=apply_failure_mode(state,modes[i%len(modes)])
 a=create_telemetry_snapshot(state,base); b=create_telemetry_snapshot(state,base)
 if a!=b: failures.append({'index':i,'error':'telemetry nondeterminism'})
 cards+=len(a['cards']); allv=create_all_station_views(state,base); views+=len(allv['views'])
 for role in roles: compute_learning_pressure(state,role,create_competency_state(),base); pressures+=1
 if not verify_ship_state(state)['valid']: failures.append({'index':i,'error':'ship state invalid'})
report={'schema':'axm.crew-station-metric-stress.v1','states':300,'metric_cards':cards,'station_views':views,'learning_pressure_snapshots':pressures,'failures':failures,'valid':not failures}; (ROOT/'docs/stress_report_v0_14_0.json').write_text(json.dumps(report,indent=2),encoding='utf-8'); print(json.dumps(report,indent=2)); raise SystemExit(0 if report['valid'] else 1)
