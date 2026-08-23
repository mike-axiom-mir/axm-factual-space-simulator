import copy, hashlib, json, unittest
from pathlib import Path
from axm_star_sim.repair_verification import (
    assess_post_repair_verification,
    build_fault_clearance_candidate,
    build_repair_gate_catalog,
    record_external_repair_execution,
    stage_repair_attempt,
    verify_repair_attempt_receipts,
)

def _proc_receipt():
    raw={"schema":"axm.failure-procedure-step-receipt.v1","procedure_id":"p","procedure_hash":"ph","session_id":"s","step_id":"last","step_index":3,"actor_role_ids":["vehicle_systems_engineer"],"evidence_ids":["x"],"hold_acknowledged":True,"completion_semantics":"record_only_not_execution","previous_receipt_hash":None,"fault_cleared":False,"repair_verified":False,"may_execute_response":False,"may_modify_runtime":False}
    raw["receipt_hash"]=hashlib.sha256(("AXM-FAILURE-PROCEDURE-STEP-RECEIPT-V1|"+json.dumps(raw,sort_keys=True,separators=(",",":"))).encode()).hexdigest()
    return raw

PROC={"schema":"axm.failure-procedure-catalog.v1","procedures":[{"source_failure_id":"power_bus_branch_fault","source_system_id":"power_distribution","procedure_id":"p","procedure_hash":"ph","status":"PROCEDURE_AVAILABLE_FOR_REVIEW"},{"source_failure_id":"crew_medical_event","source_system_id":"crew_health_medical","procedure_id":"med","procedure_hash":"mh","status":"HOLD_SPECIALIST_MEDICAL_PROCEDURE_REQUIRED"}]}
TOPO={"schema":"axm.damage-topology-catalog.v1","topologies":[{"source_failure_id":"power_bus_branch_fault","source_system_id":"power_distribution","topology_id":"t","topology_hash":"th","status":"TOPOLOGY_VIEW_AVAILABLE","access":{"status":"ACCESS_PATH_AVAILABLE_WITH_UNRESOLVED_EXTERNAL_BINDINGS","preferred_room_path":{"rooms":["engineering"],"travel_minutes":0}},"component_specificity":{"status":"SYSTEM_LEVEL_ONLY"}},{"source_failure_id":"crew_medical_event","source_system_id":"crew_health_medical","topology_id":"mt","topology_hash":"mth","status":"TOPOLOGY_VIEW_AVAILABLE","access":{"status":"HOLD_NO_PINNED_STATION_ROOM","preferred_room_path":None},"component_specificity":{"status":"SYSTEM_LEVEL_ONLY"}}]}
SESSION={"schema":"axm.failure-procedure-session.v1","procedure_id":"p","procedure_hash":"ph","session_id":"s","status":"PROCEDURE_COMPLETE_AWAIT_EXTERNAL_OUTCOME_VERIFICATION","actor_role_ids":["vehicle_systems_engineer"],"step_receipts":[],"previous_receipt_hash":None,"fault_cleared":False,"repair_verified":False}
PLAN={"plan_id":"plan-1","source_ref":"manual:approved-plan","target_system_id":"power_distribution","planned_action_summary":"externally supplied maintenance action","reversibility":"reversible_or_held","consumes_spares":False,"fabricated_part":False}
EXEC={"execution_id":"exec-1","executor_ref":"external:crew","result_claim":"repair attempted","evidence_ids":["work-log-1"]}
VERIFY_OK={"verification_id":"verify-1","source_ref":"sensor-check","evidence_ids":["post-state-1"],"independent_check_ids":["check-2"],"outcome":"effective","observed_fault_absent":True,"system_function_restored":True}
VERIFY_BAD={"verification_id":"verify-2","source_ref":"sensor-check","evidence_ids":["post-state-2"],"independent_check_ids":["check-3"],"outcome":"not_effective","observed_fault_absent":False,"system_function_restored":False}

class Tests(unittest.TestCase):
    def test_catalog_reuses_procedure_and_topology(self):
        c=build_repair_gate_catalog(PROC,TOPO)
        self.assertEqual(c["gate_count"],2)
        self.assertEqual(c["gates"][0]["status"],"READY_FOR_EXTERNAL_REPAIR_PLAN")
        self.assertEqual(c["gates"][1]["status"],"HOLD_PROCEDURE_NOT_AVAILABLE")
        self.assertFalse(c["may_clear_fault"])
    def test_stage_requires_completed_procedure(self):
        gate=build_repair_gate_catalog(PROC,TOPO)["gates"][0]
        bad=copy.deepcopy(SESSION); bad["status"]="ACTIVE_REVIEW"
        with self.assertRaises(ValueError): stage_repair_attempt(gate,bad,actor_role_ids=["vehicle_systems_engineer"],repair_plan_receipt=PLAN)
    def test_stage_refuses_unsourced_spare_consumption(self):
        gate=build_repair_gate_catalog(PROC,TOPO)["gates"][0]
        plan={**PLAN,"consumes_spares":True}
        with self.assertRaises(ValueError): stage_repair_attempt(gate,SESSION,actor_role_ids=["vehicle_systems_engineer"],repair_plan_receipt=plan)
    def test_stage_actor_must_match_completed_session(self):
        gate=build_repair_gate_catalog(PROC,TOPO)["gates"][0]
        with self.assertRaises(PermissionError):
            stage_repair_attempt(gate,SESSION,actor_role_ids=["science_anomaly_specialist"],repair_plan_receipt=PLAN)
    def test_external_execution_does_not_verify_or_clear(self):
        gate=build_repair_gate_catalog(PROC,TOPO)["gates"][0]
        a=stage_repair_attempt(gate,SESSION,actor_role_ids=["vehicle_systems_engineer"],repair_plan_receipt=PLAN)
        a=record_external_repair_execution(a,EXEC)
        self.assertEqual(a["status"],"ATTEMPT_RECORDED_AWAIT_POST_REPAIR_VERIFICATION")
        self.assertFalse(a["repair_verified"]);self.assertFalse(a["fault_cleared"])
        self.assertEqual(verify_repair_attempt_receipts(a)["status"],"PASS")
    def test_effective_verification_only_makes_clearance_eligible(self):
        gate=build_repair_gate_catalog(PROC,TOPO)["gates"][0]
        a=stage_repair_attempt(gate,SESSION,actor_role_ids=["vehicle_systems_engineer"],repair_plan_receipt=PLAN)
        a=record_external_repair_execution(a,EXEC)
        a=assess_post_repair_verification(a,VERIFY_OK)
        self.assertEqual(a["status"],"VERIFIED_EFFECTIVE_CLEARANCE_ELIGIBLE")
        self.assertTrue(a["repair_verified"]);self.assertTrue(a["fault_clearance_eligible"])
        self.assertFalse(a["fault_cleared"])
        c=build_fault_clearance_candidate(a)
        self.assertTrue(c["fault_clearance_eligible"]);self.assertFalse(c["fault_cleared"]);self.assertFalse(c["may_clear_fault"])
    def test_effective_without_independent_check_is_inconclusive(self):
        gate=build_repair_gate_catalog(PROC,TOPO)["gates"][0]
        a=stage_repair_attempt(gate,SESSION,actor_role_ids=["vehicle_systems_engineer"],repair_plan_receipt=PLAN)
        a=record_external_repair_execution(a,EXEC)
        v={**VERIFY_OK,"independent_check_ids":[]}
        a=assess_post_repair_verification(a,v)
        self.assertEqual(a["status"],"VERIFICATION_INCONCLUSIVE_FAULT_REMAINS")
        self.assertFalse(a["fault_clearance_eligible"]);self.assertFalse(a["fault_cleared"])
    def test_not_effective_is_verified_but_fault_remains(self):
        gate=build_repair_gate_catalog(PROC,TOPO)["gates"][0]
        a=stage_repair_attempt(gate,SESSION,actor_role_ids=["vehicle_systems_engineer"],repair_plan_receipt=PLAN)
        a=record_external_repair_execution(a,EXEC)
        a=assess_post_repair_verification(a,VERIFY_BAD)
        self.assertEqual(a["status"],"VERIFIED_NOT_EFFECTIVE_FAULT_REMAINS")
        self.assertTrue(a["verification_complete"]);self.assertFalse(a["repair_verified"]);self.assertFalse(a["fault_clearance_eligible"]);self.assertFalse(a["fault_cleared"])
    def test_receipt_tamper_detected(self):
        gate=build_repair_gate_catalog(PROC,TOPO)["gates"][0]
        a=stage_repair_attempt(gate,SESSION,actor_role_ids=["vehicle_systems_engineer"],repair_plan_receipt=PLAN)
        a=record_external_repair_execution(a,EXEC)
        self.assertEqual(verify_repair_attempt_receipts(a)["status"],"PASS")
        a["receipts"][0]["payload"]["result_claim"]="tampered"
        self.assertEqual(verify_repair_attempt_receipts(a)["status"],"FAIL")
    def test_inputs_not_mutated(self):
        p,t=copy.deepcopy(PROC),copy.deepcopy(TOPO); po,to=copy.deepcopy(p),copy.deepcopy(t)
        build_repair_gate_catalog(p,t)
        self.assertEqual(p,po);self.assertEqual(t,to)

    @unittest.skipUnless(
        (Path(__file__).resolve().parents[1] / "data" / "ship_failure_mode_registry.json").exists(),
        "repository registries not present in detached focused-test staging",
    )
    def test_actual_repository_catalogs_join_without_clear_authority(self):
        from axm_star_sim.damage_topology import build_damage_topology_catalog
        from axm_star_sim.failure_procedures import build_failure_procedure_catalog
        repo=Path(__file__).resolve().parents[1]
        load=lambda name: json.loads((repo/"data"/name).read_text(encoding="utf-8"))
        failures=load("ship_failure_mode_registry.json")
        stations=load("crew_station_display_registry.json")
        procedures=build_failure_procedure_catalog(failures,stations)
        topology=build_damage_topology_catalog(
            failures,
            load("ship_system_blueprint_registry.json"),
            load("ship_interface_graph.json"),
            load("ship_interior_archetype_registry.json"),
            load("room_interaction_registry.json"),
            procedure_catalog=procedures,
        )
        gates=build_repair_gate_catalog(procedures,topology)
        self.assertEqual(gates["gate_count"],procedures["procedure_count"])
        self.assertTrue(any(g["status"]=="READY_FOR_EXTERNAL_REPAIR_PLAN" for g in gates["gates"]))
        self.assertTrue(all(g["may_clear_fault"] is False for g in gates["gates"]))
        self.assertTrue(all(g["fault_cleared"] is False for g in gates["gates"]))

if __name__=="__main__": unittest.main()
