import copy
import json
import unittest
from pathlib import Path

from axm_star_sim.failure_procedures import build_failure_procedure_catalog
from axm_star_sim.living_interior_animation import build_living_interior_animation
from axm_star_sim.low_graphic_scene import build_low_graphic_3d_scene


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def context():
    return {
        "schema": "axm.living-operations-context.v1",
        "version": "0.13.0-candidate",
        "source_turn": 4,
        "source_mission_time_hours": 3.0,
        "resources": {
            "reactor_reserve_percent": 78.0,
            "sensor_health_percent": 91.0,
            "hull_integrity_percent": 96.0,
            "fuel_percent": 82.0,
            "heat_percent": 19.0,
        },
    }


class LivingInteriorAnimationTests(unittest.TestCase):
    def scene(self):
        return build_low_graphic_3d_scene(
            context(),
            load("crew_station_display_registry.json"),
            load("ship_interior_archetype_registry.json"),
        )

    def test_packet_is_deterministic_and_read_only(self):
        scene = self.scene()
        before = copy.deepcopy(scene)
        first = build_living_interior_animation(scene)
        second = build_living_interior_animation(scene)
        self.assertEqual(first, second)
        self.assertEqual(scene, before)
        self.assertEqual(first["schema"], "axm.living-interior-animation.v1")
        self.assertEqual(first["version"], "0.13.0-candidate")
        self.assertEqual(first["authority"], "read_only_living_interior_presentation")
        self.assertFalse(first["renderer_may_open_authoritative_doors"])
        self.assertFalse(first["renderer_may_move_authoritative_crew"])
        self.assertFalse(first["renderer_may_claim_physical_hardware"])
        self.assertFalse(first["renderer_may_execute_repair"])
        self.assertFalse(first["renderer_may_modify_resources"])

    def test_every_registered_room_gets_room_specific_life(self):
        packet = build_living_interior_animation(self.scene())
        profiles = {row["room_id"]: row for row in packet["room_activity_profiles"]}
        self.assertEqual(len(profiles), 7)
        self.assertIn("thermal_visual_cycle", profiles["engineering"]["activity_channels"])
        self.assertIn("hologram_scan", profiles["research_strategy"]["activity_channels"])
        self.assertIn("guide_light_chase", profiles["central_corridor"]["activity_channels"])
        self.assertTrue(all(not row["may_claim_physical_hardware"] for row in profiles.values()))

    def test_every_graph_edge_gets_non_authoritative_portal_actor(self):
        scene = self.scene()
        packet = build_living_interior_animation(scene)
        self.assertEqual(len(packet["portal_actors"]), len(scene["room_edges"]))
        self.assertTrue(all(not row["may_open_authoritative_door"] for row in packet["portal_actors"]))
        self.assertTrue(all(not row["may_claim_physical_door_design"] for row in packet["portal_actors"]))

    def test_director_walkthrough_uses_only_registered_graph_rooms(self):
        scene = self.scene()
        packet = build_living_interior_animation(scene)
        registered = {row["room_id"] for row in scene["rooms"]}
        route = packet["director_walkthrough"]["route_rooms"]
        self.assertTrue(route)
        self.assertTrue(set(route).issubset(registered))
        self.assertTrue(registered.issubset(set(route)))
        self.assertEqual(packet["director_walkthrough"]["movement_semantics"], "CAMERA_ONLY_PRESENTATION_WALKTHROUGH")
        self.assertFalse(packet["director_walkthrough"]["may_move_authoritative_crew"])

    def test_resource_channels_copy_source_values_without_inference(self):
        packet = build_living_interior_animation(self.scene())
        channels = {row["resource_id"]: row for row in packet["resource_visual_channels"]}
        self.assertEqual(channels["reactor_reserve_percent"]["source_value"], 78.0)
        self.assertIn("engineering", channels["reactor_reserve_percent"]["target_room_ids"])
        self.assertTrue(all(not row["may_modify_resource"] for row in channels.values()))
        self.assertTrue(all(not row["may_infer_missing_resource"] for row in channels.values()))

    def test_procedure_route_becomes_reenactment_track_not_crew_truth(self):
        scene = self.scene()
        scene["rehearsal_routes"] = [{
            "source_failure_id": "power_generation_degraded",
            "source_system_id": "electrical_power_generation",
            "route_rooms": ["command_deck", "central_corridor", "engineering"],
            "target_room_id": "engineering",
            "access_status": "ACCESS_PATH_AVAILABLE",
        }]
        procedures = build_failure_procedure_catalog(
            load("ship_failure_mode_registry.json"),
            load("crew_station_display_registry.json"),
        )
        packet = build_living_interior_animation(scene, procedure_catalog=procedures)
        track = packet["crew_reenactment_tracks"][0]
        self.assertEqual(track["source_role_id"], "vehicle_systems_engineer")
        self.assertEqual(track["route_rooms"][-1], "engineering")
        self.assertEqual(track["movement_semantics"], "PROCEDURE_REHEARSAL_MARKER_ONLY_NOT_AUTHORITATIVE_CREW_POSITION")
        self.assertFalse(track["may_move_authoritative_crew"])
        self.assertFalse(track["may_execute_repair"])
        self.assertFalse(track["may_claim_fault_active"])


if __name__ == "__main__":
    unittest.main()
