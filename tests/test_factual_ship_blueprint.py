import copy
import json
import unittest
from pathlib import Path

from axm_star_sim.ship_blueprint import (
    advance_ship_state,
    apply_encounter_effects,
    apply_failure_mode,
    blueprint_commitment,
    create_ship_state,
    evaluate_communications,
    evaluate_life_support,
    evaluate_power,
    evaluate_ship,
    fault_propagation_paths,
    load_blueprint,
    qualification_gap_plan,
    role_perspective_snapshot,
    task_readiness,
    validate_blueprint,
    verify_ship_state,
)


class FactualShipBlueprintTests(unittest.TestCase):
    def test_blueprint_validates(self):
        result = validate_blueprint()
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["system_count"], 22)

    def test_entire_core_system_set_exists(self):
        blueprint = load_blueprint()
        systems = {row["id"] for row in blueprint["systems"]}
        expected = {
            "primary_structure", "mmod_and_external_protection",
            "electrical_power_generation", "energy_storage", "power_distribution",
            "thermal_control", "main_propulsion", "reaction_control", "gnc",
            "avionics_cdh", "communications", "eclss_atmosphere", "water_and_waste",
            "fire_and_emergency_response", "radiation_monitoring_and_shelter",
            "docking_airlock_eva", "robotics_and_probe_operations", "external_sensors",
            "science_payload_and_analysis", "crew_health_medical",
            "logistics_maintenance_fabrication", "fault_management",
        }
        self.assertEqual(systems, expected)

    def test_unknown_vehicle_performance_stays_unknown(self):
        blueprint = load_blueprint()
        self.assertIsNone(blueprint["design_points"]["integrated_wet_mass_kg"]["value"])
        self.assertIsNone(blueprint["design_points"]["verified_delta_v_m_s"]["value"])
        propulsion = next(row for row in blueprint["systems"] if row["id"] == "main_propulsion")
        self.assertIsNone(propulsion["parameters"]["specific_impulse_s"]["value"])

    def test_catalog_facts_have_sources(self):
        blueprint = load_blueprint()
        for system in blueprint["systems"]:
            for parameter in system["parameters"].values():
                if parameter["truth_type"] == "catalog_fact":
                    self.assertTrue(parameter["source_ids"])

    def test_simulation_assumptions_are_disclosed(self):
        state = create_ship_state("ASSUMPTION-DISCLOSURE")
        self.assertEqual(state["assumption_disclosure"]["loads_kw"], "simulation_design_assumptions")
        self.assertEqual(state["assumption_disclosure"]["complete_vehicle_mass"], "unknown")

    def test_state_is_deterministic(self):
        self.assertEqual(create_ship_state("SAME"), create_ship_state("SAME"))

    def test_power_budget_is_explicit(self):
        state = create_ship_state("POWER")
        power = evaluate_power(state)
        self.assertIn("power_margin_kw", power)
        self.assertGreater(power["generated_power_kw"], 0)
        self.assertGreater(power["served_load_kw"], 0)

    def test_battery_changes_with_eclipse(self):
        state = create_ship_state("ECLIPSE")
        before = state["power"]["battery_energy_kwh"]
        state = advance_ship_state(state, 60, solar_flux_ratio=0.0)
        self.assertLess(state["power"]["battery_energy_kwh"], before)

    def test_thermal_storage_rises_under_overload(self):
        state = create_ship_state("THERMAL")
        before = state["thermal"]["thermal_storage_kwh"]
        state = advance_ship_state(
            state,
            30,
            activity_loads_kw={"science_payload_and_analysis": 30.0},
        )
        self.assertGreater(state["thermal"]["thermal_storage_kwh"], before)

    def test_water_mass_balance_advances(self):
        state = create_ship_state("WATER")
        before = state["water"]["stored_potable_water_kg"]
        state = advance_ship_state(state, 1440)
        self.assertLess(state["water"]["stored_potable_water_kg"], before)
        life = evaluate_life_support(state)
        self.assertGreater(life["estimated_water_days"], 0)

    def test_light_time_is_physical(self):
        state = create_ship_state("COMMS")
        comm = evaluate_communications(state)
        self.assertAlmostEqual(comm["one_way_light_time_s"], 1.282220382, places=6)

    def test_power_failure_is_hash_verified(self):
        state = create_ship_state("POWER-FAULT")
        state = apply_failure_mode(state, "power_generation_degraded")
        self.assertIn("power_generation_degraded", state["system_health"]["electrical_power_generation"]["active_fault_ids"])
        self.assertTrue(verify_ship_state(state)["valid"])

    def test_cabin_leak_causes_command_recall(self):
        state = apply_failure_mode(create_ship_state("LEAK"), "cabin_pressure_leak")
        self.assertIsNotNone(state["command"]["pending_recall"])
        self.assertGreater(state["atmosphere"]["pressure_leak_kpa_per_hour"], 0)

    def test_radiation_event_activates_shelter(self):
        state = apply_failure_mode(create_ship_state("RAD"), "radiation_event")
        self.assertTrue(state["radiation"]["shelter_active"])

    def test_navigation_disagreement_increases_uncertainty(self):
        state = create_ship_state("NAV")
        before = state["navigation"]["navigation_uncertainty_km"]
        state = apply_failure_mode(state, "navigation_sensor_disagreement")
        self.assertGreater(state["navigation"]["navigation_uncertainty_km"], before)

    def test_encounter_does_not_infer_hostility(self):
        state = apply_encounter_effects(create_ship_state("CONTACT"), {
            "encounter_id": "unknown-impact",
            "summary": "A fast object crosses the shield cone.",
            "observations": ["brief impact flash"],
            "effects": {"kinetic_impact_index": 4.0},
        })
        record = state["encounter_ledger"][-1]
        self.assertEqual(record["intent_assessment"], "unknown")
        self.assertFalse(record["hostility_inferred_from_damage"])

    def test_encounter_effects_couple_to_real_ship_systems(self):
        state = create_ship_state("ENCOUNTER")
        state = apply_encounter_effects(state, {
            "encounter_id": "multi-channel",
            "effects": {
                "external_thermal_load_kw": 12.0,
                "radiation_index_delta": 3.0,
                "electromagnetic_interference_fraction": 0.4,
                "navigation_uncertainty_km_delta": 9.0,
                "power_generation_loss_fraction": 0.2,
            },
        })
        self.assertEqual(state["thermal"]["extra_external_heat_kw"], 12.0)
        self.assertTrue(state["radiation"]["shelter_active"])
        self.assertLess(state["communications"]["availability"], 1.0)
        self.assertGreater(state["navigation"]["navigation_uncertainty_km"], 9.0)
        self.assertIsNotNone(state["command"]["pending_recall"])

    def test_fault_paths_show_cross_system_consequences(self):
        paths = fault_propagation_paths("electrical_power_generation")
        self.assertTrue(any(path[-1] == "eclss_atmosphere" for path in paths))
        self.assertTrue(any(path[-1] == "avionics_cdh" for path in paths))

    def test_role_perspectives_are_metric_based(self):
        state = create_ship_state("ROLES")
        engineering = role_perspective_snapshot(state, "vehicle_systems_engineer")
        navigation = role_perspective_snapshot(state, "flight_dynamics_navigation")
        self.assertIn("power_margin_kw", engineering["starting_perspective_metrics"])
        self.assertIn("navigation_uncertainty", navigation["starting_perspective_metrics"])
        self.assertNotEqual(set(engineering["starting_perspective_metrics"]), set(navigation["starting_perspective_metrics"]))

    def test_role_perspective_retains_roots_boundary(self):
        state = create_ship_state("ROOTS")
        role = role_perspective_snapshot(state, "mission_commander")
        self.assertIn("immutable_roots", role["may_not_override"])

    def test_task_readiness_detects_training_gap(self):
        state = create_ship_state("TRAINING")
        result = task_readiness(state, "communications_data_robotics", {"robotics_and_probe_operations": 5})
        self.assertFalse(result["ready"])
        self.assertEqual(result["gaps"][0]["actual"], 4)

    def test_qualification_plan_requires_evidence(self):
        state = create_ship_state("QUAL")
        plan = qualification_gap_plan(state, "vehicle_systems_engineer", {"gnc": 3})
        self.assertFalse(plan["ready_now"])
        self.assertTrue(plan["training_modules"][0]["automatic_promotion_forbidden"])
        self.assertIn("integrated_off_nominal_simulation", plan["training_modules"][0]["required_evidence"])

    def test_science_role_has_secondary_medical_assignment_in_registry(self):
        root = Path(__file__).resolve().parents[1]
        crew = json.loads((root / "data/crew_start_registry.json").read_text(encoding="utf-8"))
        assignment = crew["crew_starts"][0]["secondary_assignments"][0]
        self.assertEqual(assignment["qualification_profile_id"], "crew_medical_officer")

    def test_state_tampering_is_detected(self):
        state = create_ship_state("TAMPER")
        self.assertTrue(verify_ship_state(state)["valid"])
        tampered = copy.deepcopy(state)
        tampered["power"]["battery_energy_kwh"] += 1
        self.assertFalse(verify_ship_state(tampered)["valid"])

    def test_blueprint_commitment_stable(self):
        self.assertEqual(blueprint_commitment(), blueprint_commitment())

    def test_start_package_pins_ship_blueprint_and_interior(self):
        from axm_star_sim.bridge_visual_core import resolve_start_package, pin_start_package_for_save
        package = resolve_start_package()
        pin = pin_start_package_for_save(package)
        self.assertEqual(pin["ship_blueprint_id"], "axm.ship.frontier-survey-stack.v1")
        self.assertEqual(pin["interior_archetype_id"], "axm.interior.frontier-survey.v1")
        self.assertEqual(pin["ship_blueprint_commitment"], blueprint_commitment())

    def test_incompatible_ship_start_is_rejected(self):
        from axm_star_sim.bridge_visual_core import BridgeContractError, resolve_start_package
        with self.assertRaises(BridgeContractError):
            resolve_start_package(ship_blueprint_id="axm.ship.unregistered.v1")

    def test_safe_state_evaluation_is_explicit(self):
        state = create_ship_state("SAFE")
        for _ in range(4):
            state = apply_failure_mode(state, "power_generation_degraded")
        evaluation = evaluate_ship(state)
        self.assertIn("crew_survival_state_currently_supported", evaluation)


if __name__ == "__main__":
    unittest.main()
