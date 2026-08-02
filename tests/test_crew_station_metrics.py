import copy,unittest
from axm_star_sim.ship_blueprint import advance_ship_state,apply_encounter_effects,apply_failure_mode,create_ship_state,state_hash,validate_blueprint
from axm_star_sim.crew_station_metrics import *
class CrewStationMetricTests(unittest.TestCase):
 def test_blueprint_includes_registries(self):
  r=validate_blueprint();self.assertTrue(r['valid'],r);self.assertEqual(r['telemetry_metric_count'],78);self.assertEqual(r['station_count'],6);self.assertEqual(r['competency_skill_count'],22)
 def test_metric_ids_unique(self):
  x=[m['id'] for m in load_metric_registry()['metrics']];self.assertEqual(len(x),len(set(x)))
 def test_metrics_explain_truth(self):
  for m in load_metric_registry()['metrics']:self.assertTrue(m['meaning'] and m['truth_type'])
 def test_unknown_maneuver_not_zero(self):
  c=next(x for x in create_telemetry_snapshot(create_ship_state('U'))['cards'] if x['metric_id']=='nav.maneuver_performance_known');self.assertFalse(c['value'])
 def test_command_duet_three_surfaces(self):self.assertEqual(len(create_station_view(create_ship_state('D'),'command_duet')['surfaces']),3)
 def test_commander_sees_survival(self):
  v=create_station_view(create_ship_state('C'),'command_duet');ids={x['metric_id'] for x in v['surfaces'][0]['metric_cards']};self.assertIn('ship.survival_supported',ids)
 def test_ai_sees_integrity(self):
  v=create_station_view(create_ship_state('A'),'command_duet');ids={x['metric_id'] for x in v['surfaces'][2]['metric_cards']};self.assertIn('ship.state_integrity',ids)
 def test_engineering_coupling(self):
  ids={x['metric_id'] for x in create_station_view(create_ship_state('E'),'engineering_station')['surfaces'][0]['metric_cards']};self.assertTrue({'power.margin','thermal.margin','life.co2_margin','structure.boundary'}<=ids)
 def test_science_quality(self):
  ids={x['metric_id'] for x in create_station_view(create_ship_state('S'),'science_station')['surfaces'][0]['metric_cards']};self.assertTrue({'science.sensor_health','science.calibration_state','science.raw_data_preserved'}<=ids)
 def test_pressure_alert(self):
  s=advance_ship_state(apply_failure_mode(create_ship_state('L'),'cabin_pressure_leak'),600);v=create_station_view(s,'engineering_station');self.assertTrue(any(a['event_id']=='METRIC:life.cabin_pressure' for a in v['alert_queue']))
 def test_fault_alert_procedure(self):
  v=create_station_view(apply_failure_mode(create_ship_state('F'),'radiator_capacity_loss'),'engineering_station');a=next(x for x in v['alert_queue'] if x['event_id']=='radiator_capacity_loss');self.assertTrue(a['procedure_link_if_available'])
 def test_quality_degrades(self):
  s=create_ship_state('Q');s['system_health']['external_sensors']['availability']=.4;s['state_hash']=state_hash(s);c=next(x for x in create_telemetry_snapshot(s)['cards'] if x['metric_id']=='science.sensor_availability');self.assertEqual(c['quality']['state'],'degraded')
 def test_trend_battery_falls(self):
  p=create_ship_state('T');s=advance_ship_state(p,60,solar_flux_ratio=0);c=next(x for x in create_telemetry_snapshot(s,p)['cards'] if x['metric_id']=='power.battery_energy');self.assertEqual(c['trend'],'falling')
 def test_all_views_hash(self):
  s=create_ship_state('H');self.assertTrue(all(v['ship_state_hash']==s['state_hash'] for v in create_all_station_views(s)['views'].values()))
 def test_control_consequences(self):
  c=next(x for x in create_station_view(create_ship_state('I'),'engineering_station')['controls'] if x['id']=='load_shedding');self.assertIn('thermal.margin',c['directly_influences']);self.assertIn('science.sensor_availability',c['secondary_consequences'])
 def test_display_rules(self):
  r=load_display_registry()['display_rules'];self.assertTrue(r['stale_or_degraded_data_visible'] and r['unknown_is_not_rendered_as_zero'])
 def test_competency_starts_zero(self):
  s=create_competency_state();self.assertTrue(all(x['level']==0 for x in s['levels'].values()));self.assertTrue(verify_competency_state(s)['valid'])
 def test_exposure_not_promotion(self):
  p=compute_learning_pressure(apply_failure_mode(create_ship_state('P'),'radiator_capacity_loss'),'vehicle_systems_engineer');self.assertTrue(all(x['current_level']==0 for x in p['ranked_skills']))
 def test_thermal_pressure(self):self.assertEqual(compute_learning_pressure(apply_failure_mode(create_ship_state('TP'),'radiator_capacity_loss'),'vehicle_systems_engineer')['highest_pressure_skill_id'],'eng.thermal')
 def test_nav_pressure(self):
  top={x['skill_id'] for x in compute_learning_pressure(apply_failure_mode(create_ship_state('NP'),'navigation_sensor_disagreement'),'flight_dynamics_navigation')['ranked_skills'][:3]};self.assertIn('nav.state_estimation',top)
 def test_not_personality_claim(self):
  p=compute_learning_pressure(create_ship_state('X'),'science_anomaly_specialist');self.assertIn('not a claim about personality',p['ranked_skills'][0]['interpretation'])
 def test_evidence_chain(self):
  ship=create_ship_state('EV');c=record_competency_evidence(create_competency_state(),role_id='vehicle_systems_engineer',skill_id='eng.power_energy',evidence_type='knowledge_check',outcome='passed',ship_state_hash=ship['state_hash']);self.assertTrue(verify_competency_state(c)['valid'])
 def test_wrong_role_rejected(self):
  with self.assertRaises(CrewStationError):record_competency_evidence(create_competency_state(),role_id='mission_commander',skill_id='eng.power_energy',evidence_type='knowledge_check',outcome='passed',ship_state_hash='x')
 def test_promotion_needs_evidence(self):
  c=create_competency_state();self.assertFalse(assess_skill_promotion(c,'eng.power_energy',1)['eligible']);self.assertRaises(CrewStationError,promote_skill,c,'eng.power_energy',1)
 def test_level_one_promotion(self):
  ship=create_ship_state('PR');c=record_competency_evidence(create_competency_state(),role_id='vehicle_systems_engineer',skill_id='eng.power_energy',evidence_type='knowledge_check',outcome='passed',ship_state_hash=ship['state_hash']);c=promote_skill(c,'eng.power_energy',1);self.assertEqual(c['levels']['eng.power_energy']['level'],1)
 def test_level_five_verifier_identity(self):
  ship=create_ship_state('V');c=create_competency_state();c['levels']['eng.power_energy']['level']=4;c['state_hash']=competency_state_hash(c)
  for e in ['integrated_off_nominal_simulation','independent_operation','verifier_signoff']:c=record_competency_evidence(c,role_id='vehicle_systems_engineer',skill_id='eng.power_energy',evidence_type=e,outcome='passed',ship_state_hash=ship['state_hash'])
  self.assertIn('verifier_identity',assess_skill_promotion(c,'eng.power_energy',5)['missing'])
 def test_tamper_detected(self):
  c=record_competency_evidence(create_competency_state(),role_id='vehicle_systems_engineer',skill_id='eng.power_energy',evidence_type='knowledge_check',outcome='passed',ship_state_hash='x');c['evidence_ledger'][0]['outcome']='failed';self.assertFalse(verify_competency_state(c)['valid'])
if __name__=='__main__':unittest.main()
