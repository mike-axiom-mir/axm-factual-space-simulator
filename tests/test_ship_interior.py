import copy
import unittest

from axm_star_sim.ship_interior import (
    ShipInteriorError,
    advance_away_operations,
    answer_command_recall,
    create_interior_state,
    move_to_room,
    perform_room_interaction,
    resolve_command_recall,
    set_continuity_policy,
    shortest_room_path,
    validate_interior_archetype,
    verify_interior_state,
)


class ShipInteriorTests(unittest.TestCase):
    def test_interior_graph_is_valid_and_connected(self):
        result = validate_interior_archetype()
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["room_count"], 7)

    def test_first_interior_is_not_future_hardcode(self):
        result = validate_interior_archetype()
        self.assertEqual(result["interior_id"], "axm.interior.frontier-survey.v1")

    def test_default_is_realistic_continuity(self):
        state = create_interior_state("TEST")
        self.assertEqual(state["continuity_policy_id"], "axm.continuity.realistic.v1")

    def test_room_path_runs_through_corridor(self):
        path = shortest_room_path("command_deck", "engineering")
        self.assertEqual(path, ["command_deck", "central_corridor", "engineering"])

    def test_realistic_mode_advances_expedition_away_from_deck(self):
        state = move_to_room(create_interior_state("A"), "mess_hall")
        before = state["expedition_clock_minutes"]
        state = advance_away_operations(state, 15)
        self.assertEqual(state["expedition_clock_minutes"] - before, 15)
        self.assertGreaterEqual(len(state["routine_events_resolved"]), 3)

    def test_pause_mode_freezes_expedition_but_not_personal_time(self):
        state = create_interior_state("B")
        state = set_continuity_policy(state, "axm.continuity.pause-away.v1")
        state = move_to_room(state, "primary_quarters")
        before_expedition = state["expedition_clock_minutes"]
        before_personal = state["personal_clock_minutes"]
        state = advance_away_operations(state, 30)
        self.assertEqual(state["expedition_clock_minutes"], before_expedition)
        self.assertEqual(state["personal_clock_minutes"] - before_personal, 30)

    def test_command_required_recall_holds_irreversible_branch(self):
        state = move_to_room(create_interior_state("C"), "research_strategy")
        state = advance_away_operations(state, 5, {
            "authority_level": "command_required",
            "summary": "Unknown object requests a trajectory change.",
            "reversible": False,
        })
        self.assertIsNotNone(state["pending_command_recall"])
        self.assertEqual(state["pending_command_recall"]["crew_resolution"], "irreversible_branch_held")
        state = answer_command_recall(state)
        self.assertEqual(state["current_room_id"], "command_deck")
        state = resolve_command_recall(state, "maintain_distance", "Preserve reversibility.")
        self.assertIsNone(state["pending_command_recall"])

    def test_advisory_does_not_force_recall(self):
        state = move_to_room(create_interior_state("D"), "mess_hall")
        state = advance_away_operations(state, 5, {
            "authority_level": "advisory",
            "summary": "A weak optional signal appeared.",
        })
        self.assertIsNone(state["pending_command_recall"])
        self.assertEqual(len(state["advisories"]), 1)

    def test_consumable_duration_is_calculated(self):
        state = move_to_room(create_interior_state("E"), "mess_hall")
        state = perform_room_interaction(state, "review_consumable_duration", {
            "crew_count": 6,
            "food_kg": 180,
            "water_liters": 360,
            "food_kg_per_person_day": 1.0,
            "water_liters_per_person_day": 2.0,
        })
        result = state["interaction_history"][-1]["result"]
        self.assertEqual(result["food_days_remaining"], 30.0)
        self.assertEqual(result["water_days_remaining"], 30.0)

    def test_engineering_power_and_thermal_are_explicit(self):
        state = move_to_room(create_interior_state("F"), "engineering")
        state = perform_room_interaction(state, "inspect_power_balance", {
            "generation_kw": 60,
            "base_load_kw": 35,
            "active_load_kw": 15,
            "reserve_requirement_kw": 5,
        })
        self.assertEqual(state["interaction_history"][-1]["result"]["operational_margin_kw"], 5.0)
        state = perform_room_interaction(state, "review_thermal_margin", {
            "waste_heat_kw": 28,
            "radiator_rejection_kw": 35,
            "thermal_reserve_kw": 4,
        })
        self.assertEqual(state["interaction_history"][-1]["result"]["thermal_state"], "within_margin")

    def test_research_ranking_preserves_claim_ceiling(self):
        state = move_to_room(create_interior_state("G"), "research_strategy")
        state = perform_room_interaction(state, "compare_hypotheses", {
            "hypotheses": [
                {
                    "hypothesis_id": "instrument_drift",
                    "supporting_channels": 1,
                    "independent_replications": 0,
                    "controls_passed": 0,
                    "contradictions": 0,
                    "unresolved_controls": ["independent_hardware"],
                },
                {
                    "hypothesis_id": "unusual_chemistry",
                    "supporting_channels": 3,
                    "independent_replications": 1,
                    "controls_passed": 2,
                    "contradictions": 0,
                    "unresolved_controls": ["abiotic_pathway_test"],
                },
            ]
        })
        result = state["interaction_history"][-1]["result"]
        self.assertIn(result["claim_ceiling"], {"candidate_anomaly", "replicated_anomaly", "strong_candidate_not_proven"})
        self.assertNotEqual(result["claim_ceiling"], "confirmed_life")

    def test_fabricated_item_is_not_magical_without_validation(self):
        state = move_to_room(create_interior_state("H"), "engineering")
        state = perform_room_interaction(state, "fabricate_room_item", {
            "item_name": "Glowing anomaly sculpture",
            "material_kg": 1.5,
            "energy_kwh": 4,
            "fabrication_hours": 2,
            "intended_capability": "detect_alien_signals",
            "capability_validation": None,
        })
        item = state["inventory"][-1]
        self.assertEqual(item["status_class"], "experimental")
        self.assertIsNone(item["capability_validation"])

    def test_items_can_be_displayed_with_provenance(self):
        state = create_interior_state("I")
        item_id = state["inventory"][0]["id"]
        state = move_to_room(state, "primary_quarters")
        state = perform_room_interaction(state, "display_provenanced_item", {
            "item_id": item_id,
            "room_id": "primary_quarters",
            "display_anchor": "desk_left",
        })
        placement = state["room_item_placements"]["primary_quarters"][0]
        self.assertEqual(placement["item_id"], item_id)
        self.assertIn("placement_receipt", placement)

    def test_ai_quarters_analysis_is_offline(self):
        state = move_to_room(create_interior_state("J"), "collaborator_quarters")
        state = perform_room_interaction(state, "offline_alternative_review", {
            "case_id": "CASE-1",
            "known_evidence": ["periodic radio burst"],
            "known_alternatives": ["instrument interference", "natural plasma process"],
        })
        result = state["interaction_history"][-1]["result"]
        self.assertFalse(result["external_ai_used"])
        self.assertFalse(result["new_evidence_created"])

    def test_wrong_room_interaction_is_blocked(self):
        state = create_interior_state("K")
        with self.assertRaises(ShipInteriorError):
            perform_room_interaction(state, "inspect_power_balance", {
                "generation_kw": 10,
                "base_load_kw": 5,
                "active_load_kw": 1,
                "reserve_requirement_kw": 1,
            })

    def test_state_tamper_is_detected(self):
        state = move_to_room(create_interior_state("L"), "mess_hall")
        self.assertTrue(verify_interior_state(state)["valid"])
        tampered = copy.deepcopy(state)
        tampered["room_visit_history"][-1]["room_id"] = "engineering"
        self.assertFalse(verify_interior_state(tampered)["valid"])


if __name__ == "__main__":
    unittest.main()
