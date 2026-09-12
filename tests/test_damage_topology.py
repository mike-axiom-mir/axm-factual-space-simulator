from __future__ import annotations

import copy
import unittest
import json
from pathlib import Path

from axm_star_sim.damage_topology import (
    build_damage_topology,
    build_damage_topology_catalog,
    verify_topology_packet,
)


def fixtures():
    failures = {
        "schema": "axm.ship-failure-mode-registry.v1",
        "failure_modes": [
            {
                "id": "power_bus_branch_fault",
                "system_id": "power_distribution",
                "criticality": "high",
                "detection": ["bus_voltage_out_of_limit"],
                "effects": {"load_service_fraction": 0.72},
                "automatic_response": ["isolate_branch"],
                "command_level": "advisory",
            },
            {
                "id": "crew_medical_event",
                "system_id": "crew_health_medical",
                "criticality": "crew_survival",
                "detection": ["crew_report"],
                "effects": {},
                "automatic_response": ["assign_cmo"],
                "command_level": "command_required",
            },
        ],
    }
    blueprint = {
        "schema": "axm.ship-system-blueprint-registry.v1",
        "default_blueprint_id": "ship",
        "blueprints": [{
            "id": "ship",
            "systems": [
                {
                    "id": "power_distribution",
                    "display_name": "Power Distribution",
                    "category": "power",
                    "criticality": "crew_survival",
                    "room_bindings": ["engineering", "battery_bay"],
                    "dependencies": ["energy_storage"],
                },
                {
                    "id": "energy_storage",
                    "display_name": "Energy Storage",
                    "category": "power",
                    "criticality": "crew_survival",
                    "room_bindings": ["engineering"],
                    "dependencies": [],
                },
                {
                    "id": "crew_health_medical",
                    "display_name": "Crew Medical",
                    "category": "medical",
                    "criticality": "crew_survival",
                    "room_bindings": ["mess_hall"],
                    "dependencies": [],
                },
                {
                    "id": "logistics_maintenance_fabrication",
                    "display_name": "Maintenance",
                    "category": "maintenance",
                    "criticality": "mission_critical",
                    "room_bindings": ["engineering"],
                    "dependencies": [],
                },
            ],
        }],
    }
    interface = {
        "schema": "axm.ship-interface-graph.v1",
        "edges": [
            {"source": "energy_storage", "target": "power_distribution", "interface_type": "electrical_power"},
            {"source": "power_distribution", "target": "crew_health_medical", "interface_type": "electrical_power"},
        ],
    }
    interior = {
        "schema": "axm.ship-interior-archetype-registry.v1",
        "default_interior_id": "inside",
        "interiors": [{
            "id": "inside",
            "rooms": [
                {"id": "command_deck", "adjacent_rooms": ["central_corridor"]},
                {"id": "central_corridor", "adjacent_rooms": ["command_deck", "engineering", "mess_hall"]},
                {"id": "engineering", "adjacent_rooms": ["central_corridor"]},
                {"id": "mess_hall", "adjacent_rooms": ["central_corridor"]},
            ],
            "travel_time_minutes": {
                "command_deck|central_corridor": 1,
                "central_corridor|engineering": 2,
                "central_corridor|mess_hall": 2,
            },
        }],
    }
    interactions = {
        "schema": "axm.room-interaction-registry.v1",
        "interactions": [
            {"id": "estimate_repair_duration"},
            {"id": "fabricate_room_item"},
        ],
    }
    procedures = {
        "schema": "axm.failure-procedure-catalog.v1",
        "procedures": [
            {
                "source_failure_id": "power_bus_branch_fault",
                "procedure_id": "failure-procedure:power_bus_branch_fault:v1",
                "status": "PROCEDURE_AVAILABLE_FOR_REVIEW",
                "primary_station_id": "engineering_station",
            },
            {
                "source_failure_id": "crew_medical_event",
                "procedure_id": "failure-procedure:crew_medical_event:v1",
                "status": "HOLD_SPECIALIST_MEDICAL_PROCEDURE_REQUIRED",
                "primary_station_id": "medical_station",
            },
        ],
    }
    return failures, blueprint, interface, interior, interactions, procedures


class DamageTopologyTests(unittest.TestCase):
    def test_existing_graphs_are_composed_not_reinvented(self):
        failures, blueprint, interface, interior, interactions, procedures = fixtures()
        packet = build_damage_topology(
            failures["failure_modes"][0], blueprint, interface, interior, interactions,
            procedure=procedures["procedures"][0],
        )
        self.assertEqual(packet["source_system_id"], "power_distribution")
        self.assertEqual(
            [(row["direction"], row["neighbor_system_id"]) for row in packet["direct_interfaces"]],
            [("inbound", "energy_storage"), ("outbound", "crew_health_medical")],
        )
        self.assertEqual(packet["impact_scope"], "DIRECT_INTERFACE_NEIGHBORS_ONLY_NO_AUTOMATIC_FAILURE_PROPAGATION")

    def test_access_route_uses_existing_room_graph(self):
        failures, blueprint, interface, interior, interactions, procedures = fixtures()
        packet = build_damage_topology(
            failures["failure_modes"][0], blueprint, interface, interior, interactions,
            procedure=procedures["procedures"][0],
        )
        access = packet["access"]
        self.assertEqual(access["origin_room_id"], "engineering")
        self.assertEqual(access["preferred_room_path"]["rooms"], ["engineering"])
        self.assertEqual(access["preferred_room_path"]["travel_minutes"], 0.0)
        self.assertIn("battery_bay", access["unresolved_or_external_bindings"])
        self.assertEqual(access["status"], "ACCESS_PATH_AVAILABLE_WITH_UNRESOLVED_EXTERNAL_BINDINGS")

    def test_unknown_component_spares_are_not_invented(self):
        failures, blueprint, interface, interior, interactions, procedures = fixtures()
        packet = build_damage_topology(
            failures["failure_modes"][0], blueprint, interface, interior, interactions,
            procedure=procedures["procedures"][0],
        )
        maintenance = packet["maintenance"]
        self.assertTrue(maintenance["maintenance_system_present"])
        self.assertTrue(maintenance["repair_duration_estimator_present"])
        self.assertEqual(maintenance["component_specific_spares_status"], "UNKNOWN_COMPONENT_SPECIFICITY_NOT_PINNED")
        self.assertFalse(maintenance["may_consume_spares"])
        self.assertFalse(maintenance["may_fabricate_repair_part"])

    def test_medical_station_without_room_is_explicit_hold(self):
        failures, blueprint, interface, interior, interactions, procedures = fixtures()
        packet = build_damage_topology(
            failures["failure_modes"][1], blueprint, interface, interior, interactions,
            procedure=procedures["procedures"][1],
        )
        self.assertEqual(packet["access"]["status"], "HOLD_NO_PINNED_STATION_ROOM")
        self.assertIsNone(packet["access"]["origin_room_id"])
        self.assertFalse(packet["may_execute_repair"])

    def test_catalog_is_deterministic_and_read_only(self):
        args = fixtures()
        a = build_damage_topology_catalog(args[0], args[1], args[2], args[3], args[4], procedure_catalog=args[5])
        b = build_damage_topology_catalog(*[copy.deepcopy(v) for v in args[:5]], procedure_catalog=copy.deepcopy(args[5]))
        self.assertEqual(a, b)
        self.assertEqual(a["topology_count"], 2)
        self.assertFalse(a["may_modify_runtime"])
        self.assertFalse(a["may_clear_fault"])
        self.assertFalse(a["repair_verified"])

    def test_topology_hash_detects_tamper(self):
        failures, blueprint, interface, interior, interactions, procedures = fixtures()
        packet = build_damage_topology(
            failures["failure_modes"][0], blueprint, interface, interior, interactions,
            procedure=procedures["procedures"][0],
        )
        self.assertTrue(verify_topology_packet(packet)["valid"])
        packet["access"]["status"] = "ACCESS_PATH_AVAILABLE"
        self.assertFalse(verify_topology_packet(packet)["valid"])

    def test_source_system_missing_is_hold(self):
        failures, blueprint, interface, interior, interactions, procedures = fixtures()
        failure = copy.deepcopy(failures["failure_modes"][0])
        failure["system_id"] = "not_in_blueprint"
        packet = build_damage_topology(failure, blueprint, interface, interior, interactions)
        self.assertEqual(packet["status"], "HOLD_SOURCE_SYSTEM_NOT_IN_BLUEPRINT")
        self.assertFalse(packet["may_clear_fault"])

    def test_unmapped_only_system_is_not_declared_reachable(self):
        failures, blueprint, interface, interior, interactions, procedures = fixtures()
        blueprint = copy.deepcopy(blueprint)
        blueprint["blueprints"][0]["systems"][0]["room_bindings"] = ["external_bus_panel"]
        packet = build_damage_topology(
            failures["failure_modes"][0], blueprint, interface, interior, interactions,
            procedure=procedures["procedures"][0],
        )
        self.assertEqual(packet["access"]["status"], "HOLD_ONLY_UNMAPPED_OR_EXTERNAL_BINDINGS")
        self.assertIsNone(packet["access"]["preferred_room_path"])

    def test_inputs_are_not_mutated(self):
        args = fixtures()
        originals = copy.deepcopy(args)
        build_damage_topology_catalog(args[0], args[1], args[2], args[3], args[4], procedure_catalog=args[5])
        self.assertEqual(args, originals)

    @unittest.skipUnless(
        (Path(__file__).resolve().parents[1] / "data" / "ship_failure_mode_registry.json").exists(),
        "repository registries not present in detached focused-test staging",
    )
    def test_actual_repository_registries_compose_without_component_invention(self):
        repo_root = Path(__file__).resolve().parents[1]
        load = lambda name: json.loads((repo_root / "data" / name).read_text(encoding="utf-8"))
        failures = load("ship_failure_mode_registry.json")
        blueprint = load("ship_system_blueprint_registry.json")
        interface = load("ship_interface_graph.json")
        interior = load("ship_interior_archetype_registry.json")
        interactions = load("room_interaction_registry.json")

        catalog = build_damage_topology_catalog(failures, blueprint, interface, interior, interactions)
        expected_count = len([row for row in failures.get("failure_modes", []) if isinstance(row, dict) and row.get("id")])
        self.assertEqual(catalog["topology_count"], expected_count)
        self.assertEqual(catalog["component_specificity"], "SYSTEM_LEVEL_ONLY")
        self.assertTrue(any(str(row.get("access", {}).get("status", "")).startswith("ACCESS_PATH_AVAILABLE") for row in catalog["topologies"]))
        self.assertTrue(all(row.get("may_clear_fault") is False for row in catalog["topologies"]))
        self.assertTrue(all(row.get("repair_verified") is False for row in catalog["topologies"]))


if __name__ == "__main__":
    unittest.main()
