import copy
import unittest

from axm_star_sim.interactive_exploration import build_interactive_exploration


def sources():
    scene = {
        "schema": "axm.low-graphic-3d-scene.v1",
        "scene_hash": "scene-hash",
        "rooms": [
            {
                "room_id": "command_deck",
                "display_name": "Command Deck",
                "room_type": "command",
                "adjacent_rooms": ["engineering"],
                "ship_system_bindings": ["communications", "gnc"],
                "purpose": ["command"],
                "position_authority": "presentation_only_graph_layout_not_physical_ship_geometry",
            },
            {
                "room_id": "engineering",
                "display_name": "Engineering",
                "room_type": "technical",
                "adjacent_rooms": ["command_deck"],
                "ship_system_bindings": ["main_propulsion", "communications"],
                "purpose": ["maintenance"],
                "position_authority": "presentation_only_graph_layout_not_physical_ship_geometry",
            },
        ],
        "station_anchors": [
            {
                "station_id": "engineering_station",
                "display_name": "Engineering Station",
                "room_id": "engineering",
                "seat_role_ids": ["vehicle_systems_engineer"],
                "placement_authority": "existing_damage_topology_station_room_map_presentation_anchor",
            }
        ],
        "unresolved_station_anchors": [
            {
                "station_id": "medical_station",
                "display_name": "Medical Station",
                "room_id": None,
                "seat_role_ids": ["crew_medical_officer"],
                "placement_authority": "NO_PINNED_ROOM_FOR_STATION",
            }
        ],
    }
    interior = {
        "schema": "axm.living-interior-animation.v1",
        "animation_hash": "interior-hash",
        "portal_actors": [
            {
                "portal_id": "presentation-portal:command_deck:engineering:v1",
                "from_room_id": "command_deck",
                "to_room_id": "engineering",
                "travel_time_minutes": 1.5,
                "travel_time_authority": "interior_registry",
                "animation_semantics": "PRESENTATION_PORTAL_NOT_A_PHYSICAL_DOOR_DESIGN_OR_AUTHORITATIVE_DOOR_STATE",
            }
        ],
    }
    exterior = {
        "schema": "axm.exterior-operations-animation.v1",
        "animation_hash": "exterior-hash",
        "system_actors": [
            {
                "system_id": "main_propulsion",
                "display_name": "Main Propulsion and Orbit Change",
                "category": "propulsion",
                "criticality": "mission_critical",
                "visual_role": "main_propulsion",
                "declared_functions": ["planned trajectory changes"],
                "declared_dependencies": ["gnc"],
                "operation_state": "UNASSESSED_NO_AUTHORITATIVE_LIVE_SYSTEM_STATE_IN_PRESENTATION_SOURCE",
                "animation_semantics": "CAPABILITY_AND_REHEARSAL_ACTOR_NOT_OPERATION_EXECUTION",
            }
        ],
        "module_actors": [
            {
                "module_id": "power_propulsion_element",
                "functions": ["main propulsion"],
                "contains_rooms": [],
                "geometry_authority": "ordered_module_presentation_layout_not_physical_vehicle_dimensions",
            }
        ],
    }
    cinematic = {
        "schema": "axm.causal-cinematic-director.v1",
        "director_hash": "director-hash",
    }
    return scene, interior, exterior, cinematic


class InteractiveExplorationTests(unittest.TestCase):
    def build(self):
        return build_interactive_exploration(*sources())

    def test_catalog_is_deterministic_and_read_only(self):
        first = self.build()
        second = self.build()
        self.assertEqual(first, second)
        self.assertEqual(first["version"], "0.15.0-candidate")
        self.assertEqual(first["authority"], "read_only_interactive_exploration_presentation")
        self.assertFalse(first["renderer_may_change_authoritative_selection"])
        self.assertFalse(first["renderer_may_retarget_event"])
        self.assertFalse(first["renderer_may_execute_action"])
        self.assertFalse(first["renderer_may_execute_operation"])
        self.assertFalse(first["renderer_may_modify_world_state"])

    def test_registered_rooms_stations_systems_portals_and_exterior_are_selectable(self):
        packet = self.build()
        ids = {row["target_id"] for row in packet["targets"]}
        self.assertIn("room:command_deck", ids)
        self.assertIn("station:engineering_station", ids)
        self.assertIn("interior-system:communications", ids)
        self.assertIn("portal:presentation-portal:command_deck:engineering:v1", ids)
        self.assertIn("exterior-system:main_propulsion", ids)
        self.assertIn("module:power_propulsion_element", ids)
        self.assertEqual(packet["default_target_id"], "room:command_deck")

    def test_unresolved_station_remains_visible_hold(self):
        packet = self.build()
        target = next(row for row in packet["targets"] if row["target_id"] == "station:medical_station")
        self.assertEqual(target["selection_status"], "HOLD_NO_PINNED_ROOM_FOR_STATION")
        self.assertIsNone(target["focus_room_id"])
        self.assertIn("does not invent", target["truth_boundary"])

    def test_selection_targets_never_gain_execution_or_movement_authority(self):
        packet = self.build()
        for target in packet["targets"]:
            self.assertFalse(target["may_modify_world_state"])
            self.assertFalse(target["may_execute_action"])
            self.assertFalse(target["may_execute_operation"])
            self.assertFalse(target["may_move_authoritative_crew"])
            self.assertFalse(target["may_move_authoritative_robotics"])
            self.assertFalse(target["may_retarget_event"])

    def test_inputs_are_not_mutated(self):
        rows = sources()
        before = copy.deepcopy(rows)
        build_interactive_exploration(*rows)
        self.assertEqual(rows, before)

    def test_follow_modes_are_presentation_context_only(self):
        packet = self.build()
        self.assertEqual(
            [row["id"] for row in packet["follow_modes"]],
            ["director", "selected_target", "active_procedure", "active_event"],
        )
        self.assertTrue(packet["interaction_capabilities"]["tap_registered_room_in_cutaway"])
        self.assertFalse(packet["interaction_capabilities"]["execute_or_mutate"])


if __name__ == "__main__":
    unittest.main()
