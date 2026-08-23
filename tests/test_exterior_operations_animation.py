import copy
import json
import unittest
from pathlib import Path

from axm_star_sim.exterior_operations_animation import build_exterior_operations_animation
from axm_star_sim.failure_procedures import build_failure_procedure_catalog
from axm_star_sim.low_graphic_scene import build_low_graphic_3d_scene

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def operations_context():
    return {
        "schema": "axm.living-operations-context.v1",
        "version": "0.14.0-candidate",
        "source_turn": 7,
        "source_mission_time_hours": 5.0,
        "resources": {
            "reactor_reserve_percent": 74.0,
            "fuel_percent": 88.0,
            "heat_percent": 31.0,
            "sensor_health_percent": 92.0,
            "hull_integrity_percent": 97.0,
            "probe_count": 3,
        },
    }


def storyboard():
    return {
        "schema": "axm.main-simulator-temporal-storyboard.v1",
        "storyboard_hash": "storyboard-test-hash",
        "cues": [
            {
                "cue_id": "cue:probe-test",
                "display_index": 0,
                "turn": 7,
                "source_event_hash": "a" * 64,
                "action": "launch probe observation",
                "action_category": "science",
                "target_planet_id": "planet-b",
                "target_planet_name": "Planet B",
                "outcome_id": "probe_observation",
                "outcome_title": "Probe observation",
                "state_change_receipt": {
                    "changes": [
                        {"resource_id": "probe_count", "direction": "decrease"},
                        {"resource_id": "knowledge_points", "direction": "increase"},
                    ]
                },
                "playback_segments": [
                    {"id": "command_outbound", "display_fraction": 0.30},
                    {"id": "observation_window", "display_fraction": 0.24},
                    {"id": "telemetry_return", "display_fraction": 0.46},
                ],
                "time_mapping": "compressed_explanatory_sequence_not_physical_duration",
            }
        ],
    }


class ExteriorOperationsAnimationTests(unittest.TestCase):
    def build(self):
        stations = load("crew_station_display_registry.json")
        interior = load("ship_interior_archetype_registry.json")
        failures = load("ship_failure_mode_registry.json")
        procedures = build_failure_procedure_catalog(failures, stations)
        scene = build_low_graphic_3d_scene(
            operations_context(),
            stations,
            interior,
        )
        exterior = build_exterior_operations_animation(
            load("ship_system_blueprint_registry.json"),
            scene,
            storyboard(),
            procedure_catalog=procedures,
        )
        return scene, procedures, exterior

    def test_declared_blueprint_modules_become_presentation_actors(self):
        _, _, exterior = self.build()
        module_ids = {row["module_id"] for row in exterior["module_actors"]}
        self.assertIn("power_propulsion_element", module_ids)
        self.assertIn("docking_probe_node", module_ids)
        self.assertTrue(all(not row["may_claim_physical_geometry"] for row in exterior["module_actors"]))

    def test_external_system_roles_cover_next_visual_operations(self):
        _, _, exterior = self.build()
        roles = {row["visual_role"] for row in exterior["system_actors"]}
        self.assertTrue({"main_propulsion", "reaction_control", "communications", "docking_eva", "robotics_probe", "external_sensors"}.issubset(roles))
        self.assertTrue(all(row["operation_state"].startswith("UNASSESSED_") for row in exterior["system_actors"]))
        self.assertTrue(all(not row["may_execute_operation"] for row in exterior["system_actors"]))

    def test_probe_cue_routes_visual_focus_without_execution_claim(self):
        _, _, exterior = self.build()
        cue = exterior["cue_choreography"][0]
        self.assertEqual(cue["visual_role"], "robotics_probe")
        self.assertEqual(cue["classification_authority"], "presentation_keyword_routing_only")
        self.assertFalse(cue["may_execute_operation"])
        self.assertFalse(cue["may_retarget_event"])

    def test_resource_channels_copy_source_values_without_inference(self):
        scene, _, exterior = self.build()
        source = scene["source_runtime_resource_snapshot"]
        channels = {row["resource_id"]: row for row in exterior["resource_visual_channels"]}
        self.assertEqual(channels["fuel_percent"]["source_value"], source["fuel_percent"])
        self.assertEqual(channels["probe_count"]["source_value"], source["probe_count"])
        self.assertFalse(channels["fuel_percent"]["may_infer_missing_value"])
        self.assertFalse(channels["fuel_percent"]["may_modify_resource"])

    def test_procedure_tracks_remain_rehearsal_only(self):
        _, _, exterior = self.build()
        self.assertGreater(len(exterior["procedure_rehearsal_tracks"]), 0)
        for row in exterior["procedure_rehearsal_tracks"]:
            self.assertFalse(row["may_claim_fault_active"])
            self.assertFalse(row["may_execute_response"])
            self.assertFalse(row["may_execute_operation"])

    def test_packet_is_deterministic_and_read_only(self):
        first = self.build()[2]
        second = self.build()[2]
        self.assertEqual(first, second)
        self.assertEqual(first["animation_hash"], second["animation_hash"])
        self.assertEqual(first["authority"], "read_only_exterior_capability_and_rehearsal_presentation")
        self.assertFalse(first["renderer_may_apply_thrust"])
        self.assertFalse(first["renderer_may_dock"])
        self.assertFalse(first["renderer_may_begin_eva"])
        self.assertFalse(first["renderer_may_deploy_probe"])
        self.assertFalse(first["renderer_may_modify_resources"])


if __name__ == "__main__":
    unittest.main()
