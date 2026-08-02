import copy
import unittest

from axm_star_sim.contact_horizon import (
    ContactHorizonError,
    authorize_active_transmission,
    build_contact_actions,
    contact_horizon_snapshot,
    load_contact_horizon_registry,
    validate_contact_horizon_registry,
)
from axm_star_sim.generator import generate_system
from axm_star_sim.runtime import initial_runtime_state, resolve_turn, verify_recorded_event
from axm_star_sim.thread_engine import build_action_menu


class ContactHorizonTests(unittest.TestCase):
    def _ready_state(self):
        system = generate_system("AXM-CONTACT-HORIZON-TEST").to_dict()
        state = initial_runtime_state(system)
        state["turn"] = 100000
        work = state["contact_horizon"]["scientific_work"]
        work["total_science_actions"] = 1000
        work["independent_observation_context_ids"] = [f"context-{i}" for i in range(12)]
        work["cross_validations"] = 80
        work["false_positive_eliminations"] = 50
        work["passive_search_hours"] = 10000.0
        state["action_menu"] = build_action_menu(system, state)
        return system, state

    def test_registry_enforces_long_horizon_and_epistemic_boundaries(self):
        self.assertEqual(validate_contact_horizon_registry(), [])
        registry = load_contact_horizon_registry()
        self.assertEqual(registry["unlock_step"], 100000)
        self.assertTrue(registry["policy"]["master_seed_does_not_preselect_alien_existence_or_intent"])
        dark_forest = next(x for x in registry["hypothesis_families"] if x["id"] == "dark_forest_scenario")
        self.assertEqual(dark_forest["epistemic_class"], "fictional-philosophical scenario")
        self.assertIn("probability model", dark_forest["not_allowed"].lower())

    def test_step_99999_is_still_locked_even_with_full_work(self):
        system, state = self._ready_state()
        state["turn"] = 99999
        self.assertEqual(build_contact_actions(system, state), [])
        snap = contact_horizon_snapshot(state)
        self.assertFalse(snap["readiness"]["ready"])
        self.assertEqual(snap["steps_remaining"], 1)

    def test_step_100000_opens_search_not_contact(self):
        system, state = self._ready_state()
        actions = build_contact_actions(system, state)
        self.assertGreaterEqual(len(actions), 3)
        snap = contact_horizon_snapshot(state)
        self.assertTrue(snap["readiness"]["ready"])
        self.assertEqual(snap["evidence_stage"], 0)
        self.assertFalse(snap["confirmed_external_life"])
        self.assertFalse(snap["confirmed_external_technology"])
        self.assertFalse(snap["confirmed_external_agency"])

    def test_contact_search_event_is_replayable_and_does_not_jump_to_confirmation(self):
        system, state = self._ready_state()
        contact_action = next(a for a in state["action_menu"]["actions"] if a["action_id"].startswith("contact-horizon:"))
        event, updated = resolve_turn(
            system=system,
            state=state,
            action=contact_action["action_id"],
            entropy_mode="deterministic",
        )
        check, rebuilt = verify_recorded_event(system, state, event)
        self.assertTrue(check["valid"], check)
        self.assertEqual(rebuilt, updated)
        self.assertIn("contact_horizon_before", event)
        self.assertIn("contact_horizon_after", event)
        self.assertLessEqual(event["contact_horizon_after"]["evidence_stage"], 2)
        self.assertFalse(event["contact_horizon_after"]["confirmed_external_agency"])

    def test_active_transmission_fails_closed_before_confirmed_agency(self):
        _system, state = self._ready_state()
        with self.assertRaises(ContactHorizonError):
            authorize_active_transmission(state, {
                "human_consent": True,
                "ai_recommendation_recorded": True,
                "reversibility_review": True,
                "risk_review": True,
            })

    def test_master_seed_change_does_not_create_hidden_contact_truth(self):
        first = initial_runtime_state(generate_system("AXM-CONTACT-A").to_dict())["contact_horizon"]
        second = initial_runtime_state(generate_system("AXM-CONTACT-B").to_dict())["contact_horizon"]
        self.assertEqual(first["candidate_id"], None)
        self.assertEqual(second["candidate_id"], None)
        self.assertEqual(first["candidate_classes"], [])
        self.assertEqual(second["candidate_classes"], [])
        self.assertIn("No hidden alien species", first["epistemic_contract"]["seed_scope"])

    def test_registry_rejects_early_unlock(self):
        registry = copy.deepcopy(load_contact_horizon_registry())
        registry["unlock_step"] = 99999
        with self.assertRaises(ContactHorizonError):
            validate_contact_horizon_registry(registry)


if __name__ == "__main__":
    unittest.main()
