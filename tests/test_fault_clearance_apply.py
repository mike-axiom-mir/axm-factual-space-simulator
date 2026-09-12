import copy
import json
import unittest
from pathlib import Path

from axm_star_sim.fault_clearance_apply import (
    AUTHORITY_POLICY_ID,
    build_clearance_apply_contract,
    build_clearance_apply_contract_catalog,
    required_reconciliation_paths,
    _active_command_required_faults,
    _validate_authorization,
    _validate_reconciliation,
    apply_verified_fault_clearance,
)

FAILURE = {
    "id":"power_bus_branch_fault",
    "system_id":"power_distribution",
    "effects":{"load_service_fraction":0.72},
    "command_level":"advisory",
}
GATE = {
    "schema":"axm.repair-verification-gate.v1",
    "gate_id":"repair-gate:power_bus_branch_fault:v1",
    "gate_hash":"g",
    "source_failure_id":"power_bus_branch_fault",
    "source_system_id":"power_distribution",
    "status":"READY_FOR_EXTERNAL_REPAIR_PLAN",
}
CANDIDATE = {
    "candidate_hash":"cand",
    "source_failure_id":"power_bus_branch_fault",
    "source_system_id":"power_distribution",
}
STATE = {
    "state_hash":"state",
    "system_health":{"power_distribution":{"availability":0.72,"mode":"faulted"}},
}

class ClearanceFocusedTests(unittest.TestCase):
    def test_required_paths_derive_from_existing_effect_map(self):
        self.assertEqual(
            required_reconciliation_paths(FAILURE),
            ["system_health.power_distribution.availability","system_health.power_distribution.mode"],
        )

    def test_unknown_effect_mapping_holds(self):
        bad=copy.deepcopy(FAILURE); bad["effects"]["mystery_effect"]=1
        with self.assertRaises(ValueError): required_reconciliation_paths(bad)

    def test_contract_is_candidate_policy_not_silent_authority(self):
        c=build_clearance_apply_contract(GATE,command_level="advisory",primary_role_id="vehicle_systems_engineer")
        self.assertEqual(c["status"],"ENGINE_AVAILABLE_REQUIRES_VERIFIED_CANDIDATE_AND_LIVE_SHIP_STATE")
        self.assertEqual(c["candidate_authority_policy"]["truth_status"],"simulation_policy_candidate_not_canon")
        self.assertFalse(c["fault_cleared"])

    def test_catalog_preserves_upstream_hold(self):
        held=copy.deepcopy(GATE);held["status"]="HOLD_NO_PINNED_REPAIR_ACCESS"
        cat=build_clearance_apply_contract_catalog({"schema":"axm.repair-verification-gate-catalog.v1","gates":[held]})
        self.assertEqual(cat["contracts"][0]["status"],"HOLD_UPSTREAM_REPAIR_GATE")

    def test_advisory_requires_primary_role(self):
        auth={"authorization_id":"a","source_ref":"x","candidate_hash":"cand","state_hash_before":"state","decision":"authorize_fault_clearance_apply","actor_role_ids":["mission_commander"],"authority_policy_id":AUTHORITY_POLICY_ID}
        with self.assertRaises(PermissionError):
            _validate_authorization(auth,candidate=CANDIDATE,state_hash_before="state",command_level="advisory",primary_role_id="vehicle_systems_engineer")

    def test_command_required_needs_commander_plus_primary(self):
        auth={"authorization_id":"a","source_ref":"x","candidate_hash":"cand","state_hash_before":"state","decision":"authorize_fault_clearance_apply","actor_role_ids":["vehicle_systems_engineer"],"authority_policy_id":AUTHORITY_POLICY_ID}
        with self.assertRaises(PermissionError):
            _validate_authorization(auth,candidate=CANDIDATE,state_hash_before="state",command_level="command_required",primary_role_id="vehicle_systems_engineer")
        auth["actor_role_ids"].append("mission_commander")
        self.assertEqual(len(_validate_authorization(auth,candidate=CANDIDATE,state_hash_before="state",command_level="command_required",primary_role_id="vehicle_systems_engineer")),64)

    def test_reconciliation_requires_exact_paths_and_evidence(self):
        rec={"reconciliation_id":"r","source_ref":"s","candidate_hash":"cand","state_hash_before":"state","source_failure_id":"power_bus_branch_fault","source_system_id":"power_distribution","updates":[
            {"path":"system_health.power_distribution.availability","expected_current_value":0.72,"verified_value":1.0,"evidence_ids":["voltage-test"]},
            {"path":"system_health.power_distribution.mode","expected_current_value":"faulted","verified_value":"nominal","evidence_ids":["system-check"]},
        ]}
        updates,h=_validate_reconciliation(rec,state=STATE,failure_mode=FAILURE,candidate=CANDIDATE)
        self.assertEqual(len(updates),2);self.assertEqual(len(h),64)

    def test_reconciliation_rejects_unapproved_mutation(self):
        rec={"reconciliation_id":"r","source_ref":"s","candidate_hash":"cand","state_hash_before":"state","source_failure_id":"power_bus_branch_fault","source_system_id":"power_distribution","updates":[
            {"path":"system_health.power_distribution.availability","expected_current_value":0.72,"verified_value":1.0,"evidence_ids":["x"]},
            {"path":"system_health.power_distribution.mode","expected_current_value":"faulted","verified_value":"nominal","evidence_ids":["y"]},
            {"path":"power.battery_energy_kwh","expected_current_value":1,"verified_value":999,"evidence_ids":["z"]},
        ]}
        with self.assertRaises(ValueError): _validate_reconciliation(rec,state={**STATE,"power":{"battery_energy_kwh":1}},failure_mode=FAILURE,candidate=CANDIDATE)

    def test_reconciliation_rejects_stale_precondition(self):
        rec={"reconciliation_id":"r","source_ref":"s","candidate_hash":"cand","state_hash_before":"state","source_failure_id":"power_bus_branch_fault","source_system_id":"power_distribution","updates":[
            {"path":"system_health.power_distribution.availability","expected_current_value":0.5,"verified_value":1.0,"evidence_ids":["x"]},
            {"path":"system_health.power_distribution.mode","expected_current_value":"faulted","verified_value":"nominal","evidence_ids":["y"]},
        ]}
        with self.assertRaises(ValueError): _validate_reconciliation(rec,state=STATE,failure_mode=FAILURE,candidate=CANDIDATE)

    def test_verified_fraction_out_of_range_is_refused(self):
        rec={"reconciliation_id":"r","source_ref":"s","candidate_hash":"cand","state_hash_before":"state","source_failure_id":"power_bus_branch_fault","source_system_id":"power_distribution","updates":[
            {"path":"system_health.power_distribution.availability","expected_current_value":0.72,"verified_value":1.5,"evidence_ids":["x"]},
            {"path":"system_health.power_distribution.mode","expected_current_value":"faulted","verified_value":"nominal","evidence_ids":["y"]},
        ]}
        with self.assertRaises(ValueError): _validate_reconciliation(rec,state=STATE,failure_mode=FAILURE,candidate=CANDIDATE)

    def test_other_command_required_faults_are_detectable_for_recall_retarget(self):
        state={"system_health":{"a":{"active_fault_ids":["f1"]},"b":{"active_fault_ids":["f2"]}}}
        registry={"failure_modes":[
            {"id":"f1","command_level":"command_required"},
            {"id":"f2","command_level":"advisory"},
        ]}
        self.assertEqual(_active_command_required_faults(state,registry),[("f1","a")])

    @unittest.skipUnless(
        (Path(__file__).resolve().parents[1] / "data" / "ship_failure_mode_registry.json").exists(),
        "repository registries not present in detached focused-test staging",
    )
    def test_actual_authoritative_ship_state_clearance_roundtrip(self):
        from axm_star_sim.damage_topology import build_damage_topology
        from axm_star_sim.failure_procedures import (
            build_failure_procedure, start_procedure_session, submit_procedure_step,
        )
        from axm_star_sim.repair_verification import (
            assess_post_repair_verification, build_fault_clearance_candidate, build_repair_gate,
            record_external_repair_execution, stage_repair_attempt,
        )
        from axm_star_sim.ship_blueprint import (
            apply_failure_mode, create_ship_state, load_failure_registry, verify_ship_state,
        )

        root=Path(__file__).resolve().parents[1]
        load=lambda name: json.loads((root/"data"/name).read_text(encoding="utf-8"))
        failures=load_failure_registry()
        failure=next(row for row in failures["failure_modes"] if row["id"]=="power_generation_degraded")
        stations=load("crew_station_display_registry.json")
        blueprint=load("ship_system_blueprint_registry.json")
        interface=load("ship_interface_graph.json")
        interior=load("ship_interior_archetype_registry.json")
        interactions=load("room_interaction_registry.json")

        before=create_ship_state("v0.8-authoritative-clearance-test")
        faulted=apply_failure_mode(before,failure["id"])
        self.assertIn(failure["id"],faulted["system_health"][failure["system_id"]]["active_fault_ids"])
        self.assertTrue(verify_ship_state(faulted)["valid"])

        procedure=build_failure_procedure(failure,stations)
        role=procedure["primary_role_id"]
        session=start_procedure_session(procedure,actor_role_ids=[role],trigger_receipt={"id":"fault-trigger"})
        for step in procedure["steps"]:
            session=submit_procedure_step(
                procedure,session,actor_role_ids=[role],
                evidence_ids=list(step["required_evidence_ids"]),
                hold_acknowledged=bool(step.get("hold_point")),
            )
        self.assertEqual(session["status"],"PROCEDURE_COMPLETE_AWAIT_EXTERNAL_OUTCOME_VERIFICATION")

        topology=build_damage_topology(
            failure,blueprint,interface,interior,interactions,procedure=procedure,
        )
        gate=build_repair_gate(procedure,topology)
        self.assertEqual(gate["status"],"READY_FOR_EXTERNAL_REPAIR_PLAN")
        attempt=stage_repair_attempt(
            gate,session,actor_role_ids=[role],repair_plan_receipt={
                "plan_id":"plan-pwr-gen-1","source_ref":"verified-maintenance-plan",
                "target_system_id":failure["system_id"],
                "planned_action_summary":"Execute the externally sourced maintenance plan and preserve measurements.",
                "reversibility":"bounded_external_maintenance_plan",
                "consumes_spares":False,"fabricated_part":False,
            },
        )
        attempt=record_external_repair_execution(attempt,{
            "execution_id":"exec-1","executor_ref":"qualified-maintenance-executor",
            "result_claim":"repair completed; verification pending",
            "evidence_ids":["execution-log-1"],
        })
        attempt=assess_post_repair_verification(attempt,{
            "verification_id":"verify-1","source_ref":"post-repair-instrument-check",
            "evidence_ids":["generation-measurement-1"],
            "independent_check_ids":["independent-power-crosscheck-1"],
            "outcome":"effective","observed_fault_absent":True,"system_function_restored":True,
        })
        candidate=build_fault_clearance_candidate(attempt)

        updates=[]
        for path in required_reconciliation_paths(failure):
            cur=faulted
            for part in path.split('.'):
                cur=cur[part]
            verified="nominal" if path.endswith(".mode") else 1.0
            updates.append({
                "path":path,"expected_current_value":copy.deepcopy(cur),"verified_value":verified,
                "evidence_ids":[f"verified-state:{path}"],
            })
        reconciliation={
            "reconciliation_id":"reconcile-1","source_ref":"post-repair-authoritative-state-observation",
            "candidate_hash":candidate["candidate_hash"],"state_hash_before":faulted["state_hash"],
            "source_failure_id":failure["id"],"source_system_id":failure["system_id"],
            "updates":updates,
        }
        authorization={
            "authorization_id":"auth-1","source_ref":"candidate-policy-test-authorization",
            "candidate_hash":candidate["candidate_hash"],"state_hash_before":faulted["state_hash"],
            "decision":"authorize_fault_clearance_apply","actor_role_ids":[role],
            "authority_policy_id":AUTHORITY_POLICY_ID,
        }
        cleared,receipt=apply_verified_fault_clearance(
            faulted,candidate=candidate,repair_attempt=attempt,procedure=procedure,
            reconciliation_receipt=reconciliation,authorization_receipt=authorization,
        )
        self.assertNotIn(failure["id"],cleared["system_health"][failure["system_id"]]["active_fault_ids"])
        self.assertEqual(cleared["system_health"][failure["system_id"]]["mode"],"nominal")
        self.assertEqual(cleared["system_health"][failure["system_id"]]["availability"],1.0)
        self.assertEqual(cleared["fault_ledger"][-1]["record_type"],"verified_clearance")
        self.assertTrue(receipt["fault_cleared"]);self.assertTrue(receipt["repair_verified"])
        self.assertTrue(verify_ship_state(cleared)["valid"])
        self.assertNotEqual(cleared["state_hash"],faulted["state_hash"])
        self.assertIn(failure["id"],faulted["system_health"][failure["system_id"]]["active_fault_ids"])

if __name__=="__main__": unittest.main()
