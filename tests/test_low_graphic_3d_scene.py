import copy
import json
import unittest
from pathlib import Path

from axm_star_sim.low_graphic_scene import build_low_graphic_3d_scene


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def operations_context():
    return {
        "schema": "axm.living-operations-context.v1",
        "version": "0.12.0-candidate",
        "source_turn": 4,
        "source_mission_time_hours": 3.0,
        "resources": {
            "reactor_reserve_percent": 78.0,
            "sensor_health_percent": 91.0,
            "hull_integrity_percent": 96.0,
        },
    }


class LowGraphic3DSceneTests(unittest.TestCase):
    def build(self, topology=None):
        return build_low_graphic_3d_scene(
            operations_context(),
            load("crew_station_display_registry.json"),
            load("ship_interior_archetype_registry.json"),
            damage_topology_catalog=topology,
        )

    def test_scene_uses_registered_interior_graph(self):
        scene = self.build()
        self.assertEqual(scene["schema"], "axm.low-graphic-3d-scene.v1")
        self.assertEqual(scene["version"], "0.12.0-candidate")
        self.assertEqual(scene["interior_id"], "axm.interior.frontier-survey.v1")
        self.assertEqual(scene["room_count"], 7)
        ids = {row["room_id"] for row in scene["rooms"]}
        self.assertEqual(ids, {"command_deck", "central_corridor", "mess_hall", "engineering", "research_strategy", "primary_quarters", "collaborator_quarters"})

    def test_layout_is_deterministic_and_explicitly_not_physical_geometry(self):
        first = self.build()
        second = self.build()
        self.assertEqual(first, second)
        self.assertEqual(first["scene_hash"], second["scene_hash"])
        self.assertTrue(all(row["position_authority"] == "presentation_only_graph_layout_not_physical_ship_geometry" for row in first["rooms"]))
        self.assertTrue(all(not row["may_claim_physical_dimensions"] for row in first["rooms"]))

    def test_station_mapping_reuses_existing_topology_map_and_keeps_medical_gap_visible(self):
        scene = self.build()
        placed = {row["station_id"]: row["room_id"] for row in scene["station_anchors"]}
        self.assertEqual(placed["engineering_station"], "engineering")
        self.assertEqual(placed["science_station"], "research_strategy")
        self.assertEqual(placed["navigation_station"], "command_deck")
        unresolved = {row["station_id"] for row in scene["unresolved_station_anchors"]}
        self.assertIn("medical_station", unresolved)

    def test_rehearsal_route_never_becomes_active_fault_truth(self):
        topology = {
            "schema": "axm.damage-topology-catalog.v1",
            "topologies": [{
                "source_failure_id": "power_generation_degraded",
                "source_system_id": "electrical_power_generation",
                "source_criticality": "high",
                "access": {
                    "status": "ACCESS_PATH_AVAILABLE",
                    "preferred_room_path": {
                        "target_room_id": "engineering",
                        "rooms": ["command_deck", "central_corridor", "engineering"],
                    },
                },
            }],
        }
        scene = self.build(topology)
        route = scene["rehearsal_routes"][0]
        self.assertEqual(route["target_room_id"], "engineering")
        self.assertEqual(route["route_rooms"][-1], "engineering")
        self.assertEqual(route["animation_semantics"], "REHEARSAL_ROUTE_ONLY_NOT_ACTIVE_FAULT_STATE")
        self.assertFalse(route["may_claim_fault_active"])
        self.assertFalse(route["may_execute_repair"])

    def test_scene_is_read_only_and_input_preserving(self):
        context = operations_context()
        stations = load("crew_station_display_registry.json")
        interior = load("ship_interior_archetype_registry.json")
        before = copy.deepcopy((context, stations, interior))
        scene = build_low_graphic_3d_scene(context, stations, interior)
        self.assertEqual((context, stations, interior), before)
        self.assertEqual(scene["authority"], "read_only_visual_projection")
        self.assertTrue(scene["renderer_may_animate"])
        self.assertFalse(scene["renderer_may_modify_runtime"])
        self.assertFalse(scene["renderer_may_move_authoritative_crew"])
        self.assertFalse(scene["renderer_may_claim_fault_active_from_rehearsal"])
        self.assertFalse(scene["renderer_may_clear_fault"])
        self.assertFalse(scene["renderer_may_exit_safe_state"])
        self.assertFalse(scene["renderer_may_restore_resources"])

    def test_unknown_room_edge_fails_closed(self):
        interior = load("ship_interior_archetype_registry.json")
        interior["interiors"][0]["rooms"][0]["adjacent_rooms"].append("invented_room")
        with self.assertRaises(ValueError):
            build_low_graphic_3d_scene(operations_context(), load("crew_station_display_registry.json"), interior)


if __name__ == "__main__":
    unittest.main()
