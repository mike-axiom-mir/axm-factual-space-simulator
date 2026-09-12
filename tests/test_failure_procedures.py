import copy
import unittest

from axm_star_sim.failure_procedures import (
    build_failure_procedure,
    build_failure_procedure_catalog,
    resume_held_session,
    start_procedure_session,
    submit_procedure_step,
    verify_procedure_receipts,
)

STATIONS = {
    "schema":"axm.crew-station-display-registry.v1","registry_version":"0.14.0",
    "stations":[
        {"id":"command_duet","seat_role_ids":["mission_commander","ai_systems_integrator"]},
        {"id":"engineering_station","seat_role_ids":["vehicle_systems_engineer"]},
        {"id":"navigation_station","seat_role_ids":["flight_dynamics_navigation"]},
        {"id":"communications_station","seat_role_ids":["communications_data_robotics"]},
        {"id":"medical_station","seat_role_ids":["crew_medical_officer"]},
    ],
}
FAILURE = {"id":"navigation_sensor_disagreement","system_id":"gnc","criticality":"high","detection":["state_estimator_residual","sensor_cross_check_failure"],"effects":{"navigation_uncertainty_km_delta":8.0},"automatic_response":["reject_outlier","increase_uncertainty","hold_high_consequence_maneuvers"],"command_level":"command_required"}
ADVISORY = {"id":"power_generation_degraded","system_id":"electrical_power_generation","criticality":"high","detection":["generated_power_below_expected"],"effects":{"generation_multiplier":.55},"automatic_response":["recompute_power_budget"],"command_level":"advisory"}
MEDICAL = {"id":"crew_medical_event","system_id":"crew_health_medical","criticality":"crew_survival","detection":["crew_report"],"effects":{"available_human_crew_delta":-1},"automatic_response":["assign_cmo","stabilize_patient"],"command_level":"command_required"}
REGISTRY={"schema":"axm.ship-failure-mode-registry.v1","registry_version":"0.13.0","failure_modes":[FAILURE,ADVISORY,MEDICAL]}

class FailureProcedureTests(unittest.TestCase):
    def test_catalog_deterministic(self):
        a=build_failure_procedure_catalog(REGISTRY,STATIONS);b=build_failure_procedure_catalog(REGISTRY,STATIONS)
        self.assertEqual(a,b);self.assertEqual(a["procedure_count"],3);self.assertFalse(a["may_clear_fault"])

    def test_navigation_routes_to_navigation(self):
        p=build_failure_procedure(FAILURE,STATIONS)
        self.assertEqual(p["primary_station_id"],"navigation_station")
        self.assertEqual(p["primary_role_id"],"flight_dynamics_navigation")
        self.assertEqual(p["steps"][-1]["step_id"],"request-command-authority")
        self.assertTrue(p["steps"][-1]["hold_point"])

    def test_advisory_never_executes(self):
        p=build_failure_procedure(ADVISORY,STATIONS)
        self.assertEqual(p["steps"][-1]["step_id"],"record-advisory-disposition")
        for step in p["steps"]:
            self.assertFalse(step["may_execute_response"]);self.assertFalse(step["may_clear_fault"])

    def test_medical_is_specialist_hold(self):
        p=build_failure_procedure(MEDICAL,STATIONS)
        self.assertEqual(p["status"],"HOLD_SPECIALIST_MEDICAL_PROCEDURE_REQUIRED")
        self.assertEqual(p["steps"],[])
        with self.assertRaises(ValueError):
            start_procedure_session(p,actor_role_ids=["crew_medical_officer"],trigger_receipt={"id":"x"})

    def test_missing_evidence_holds_without_advance(self):
        p=build_failure_procedure(FAILURE,STATIONS)
        s=start_procedure_session(p,actor_role_ids=["flight_dynamics_navigation"],trigger_receipt={"id":"f"})
        held=submit_procedure_step(p,s,actor_role_ids=["flight_dynamics_navigation"],evidence_ids=[],hold_acknowledged=True)
        self.assertEqual(held["status"],"HOLD");self.assertEqual(held["current_step_index"],0);self.assertEqual(held["step_receipts"],[])

    def test_explicit_hold_required(self):
        p=build_failure_procedure(FAILURE,STATIONS)
        s=start_procedure_session(p,actor_role_ids=["flight_dynamics_navigation"],trigger_receipt={"id":"f"})
        held=submit_procedure_step(p,s,actor_role_ids=["flight_dynamics_navigation"],evidence_ids=FAILURE["detection"],hold_acknowledged=False)
        self.assertEqual(held["status"],"HOLD")
        s2=resume_held_session(held)
        advanced=submit_procedure_step(p,s2,actor_role_ids=["flight_dynamics_navigation"],evidence_ids=FAILURE["detection"],hold_acknowledged=True)
        self.assertEqual(advanced["current_step_index"],1)

    def test_complete_never_clears_fault(self):
        p=build_failure_procedure(ADVISORY,STATIONS)
        s=start_procedure_session(p,actor_role_ids=["vehicle_systems_engineer"],trigger_receipt={"id":"f"})
        for evidence,ack in [(["generated_power_below_expected"],True),(["automatic_response_receipt"],False),(["read_only_runtime_snapshot","fault_effect_snapshot"],True),(["advisory_disposition_receipt"],False)]:
            s=submit_procedure_step(p,s,actor_role_ids=["vehicle_systems_engineer"],evidence_ids=evidence,hold_acknowledged=ack)
        self.assertEqual(s["status"],"PROCEDURE_COMPLETE_AWAIT_EXTERNAL_OUTCOME_VERIFICATION")
        self.assertFalse(s["fault_cleared"]);self.assertFalse(s["repair_verified"])
        self.assertEqual(verify_procedure_receipts(s)["status"],"PASS")

    def test_tamper_detected(self):
        p=build_failure_procedure(ADVISORY,STATIONS)
        s=start_procedure_session(p,actor_role_ids=["vehicle_systems_engineer"],trigger_receipt={"id":"f"})
        s=submit_procedure_step(p,s,actor_role_ids=["vehicle_systems_engineer"],evidence_ids=["generated_power_below_expected"],hold_acknowledged=True)
        self.assertEqual(verify_procedure_receipts(s)["status"],"PASS")
        s["step_receipts"][0]["evidence_ids"].append("tamper")
        self.assertEqual(verify_procedure_receipts(s)["status"],"FAIL")

    def test_station_registry_mismatch_holds_build(self):
        broken=copy.deepcopy(STATIONS);broken["stations"]=[r for r in broken["stations"] if r["id"]!="navigation_station"]
        with self.assertRaises(ValueError):build_failure_procedure(FAILURE,broken)

if __name__=="__main__":
    unittest.main()
