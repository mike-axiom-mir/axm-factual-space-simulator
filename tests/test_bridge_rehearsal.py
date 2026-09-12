import copy
import unittest

from axm_star_sim.bridge_rehearsal import build_rehearsal_catalog
from axm_star_sim.living_operations_bridge import build_operations_context, enrich_storyboard


class BridgeRehearsalTests(unittest.TestCase):
    def runtime(self):
        return {
            "schema":"axm.adventure-runtime.v4","system_id":"demo-system","turn":4,"mission_time_hours":3.0,
            "resources":{"sensor_health_percent":94.0},
            "threads":{"communication-latency":{"title":"Command and telemetry light-time","kind":"communication-latency","status":"active","depth":1}},
            "open_threads":["communication-latency"],
            "action_menu":{"menu_version":5,"actions":[{"action_id":"communication-latency:hold","label":"Hold course until delayed telemetry arrives","category":"patient_observation","source_thread":"communication-latency","target_planet_id":"planet-3","intent":"Respect one-way light time instead of inventing immediate feedback.","priority":0.98}]},
        }

    def storyboard(self):
        return {"schema":"axm.main-simulator-temporal-storyboard.v1","system_id":"demo-system","mission_time_hours":3.0,"cues":[{"turn":4}]}

    def test_catalog_is_deterministic(self):
        context=build_operations_context(self.runtime())
        self.assertEqual(build_rehearsal_catalog(context),build_rehearsal_catalog(context))

    def test_rehearsal_never_executes(self):
        rehearsal=build_rehearsal_catalog(build_operations_context(self.runtime()))["rehearsals"][0]
        self.assertFalse(rehearsal["may_execute_action"])
        self.assertTrue(all(not step["may_execute_action"] for step in rehearsal["steps"]))

    def test_light_time_action_is_flagged(self):
        rehearsal=build_rehearsal_catalog(build_operations_context(self.runtime()))["rehearsals"][0]
        self.assertIn("light_time_sensitive",rehearsal["context_flags"])

    def test_command_authority_is_a_hold_not_execution(self):
        final=build_rehearsal_catalog(build_operations_context(self.runtime()))["rehearsals"][0]["steps"][-1]
        self.assertEqual(final["station_role"],"command")
        self.assertTrue(final["hold_point"])
        self.assertEqual(final["completion_semantics"],"request_only_not_execution")

    def test_enrich_storyboard_adds_rehearsal_without_mutation(self):
        runtime,board=self.runtime(),self.storyboard()
        before_runtime,before_board=copy.deepcopy(runtime),copy.deepcopy(board)
        out=enrich_storyboard(board,runtime)
        self.assertEqual(runtime,before_runtime)
        self.assertEqual(board,before_board)
        self.assertEqual(out["bridge_rehearsal"]["rehearsal_count"],1)
        self.assertFalse(out["living_operations"]["may_execute_action"])

    def test_system_mismatch_holds(self):
        runtime,board=self.runtime(),self.storyboard();board["system_id"]="other"
        with self.assertRaises(ValueError):
            enrich_storyboard(board,runtime)


if __name__=="__main__":
    unittest.main()
