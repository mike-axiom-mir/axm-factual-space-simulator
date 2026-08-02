import copy
import unittest

from axm_star_sim.bridge_visual_core import (
    BridgeContractError,
    first_bridge_reference_layout,
    make_reconstruction_packet,
    pin_start_package_for_save,
    resolve_start_package,
    validate_layout_packet,
)


class BridgeVisualCoreTests(unittest.TestCase):
    def test_first_start_resolves(self):
        package = resolve_start_package()
        self.assertEqual(package["bridge_archetype"]["id"], "axm.bridge.frontier-survey.v1")
        self.assertEqual(package["timeline_start"]["id"], "axm.timeline.near-future-factual.v1")
        self.assertEqual(package["crew_start"]["id"], "axm.crew.first-expedition.v1")

    def test_first_bridge_is_not_universal_hardcode(self):
        package = resolve_start_package()
        self.assertEqual(package["bridge_archetype"]["scope"], "First of many possible vessels and bridge starts.")
        rule = package["experience_contract"]["extensibility_rule"]
        self.assertIn("new vessel archetype", rule["new_ship"])

    def test_valid_paint_layout_passes(self):
        layout = first_bridge_reference_layout()
        result = validate_layout_packet(layout, layout["start_pin"])
        self.assertTrue(result["valid"], result)

    def test_generic_site_regression_fails(self):
        layout = first_bridge_reference_layout()
        layout["primary_interface_pattern"] = "generic_website_dashboard"
        result = validate_layout_packet(layout, layout["start_pin"])
        self.assertFalse(result["valid"])

    def test_missing_crew_anchor_fails(self):
        layout = first_bridge_reference_layout()
        layout["semantic_anchor_ids"].remove("science")
        result = validate_layout_packet(layout, layout["start_pin"])
        self.assertFalse(result["valid"])

    def test_visual_upgrade_preserves_semantics(self):
        package = resolve_start_package()
        pin = pin_start_package_for_save(package)
        packet = make_reconstruction_packet(
            pin,
            historical_state_hash="a" * 64,
            target_render_profile_id="axm.render.holodeck-reconstruction.v1",
        )
        self.assertEqual(packet["semantic_anchor_ids"], pin["semantic_anchor_ids"])
        self.assertIn("historical_state", packet["renderer_may_not_change"])

    def test_pin_is_versioned(self):
        pin = pin_start_package_for_save(resolve_start_package())
        self.assertEqual(pin["bridge_archetype_version"], 1)
        self.assertEqual(pin["timeline_start_version"], 1)
        self.assertEqual(pin["crew_start_version"], 1)
        self.assertEqual(pin["migration_policy"], "immutable_semantics_new_versions_only")

    def test_unknown_future_component_is_rejected_until_registered(self):
        with self.assertRaises(BridgeContractError):
            resolve_start_package(bridge_archetype_id="axm.bridge.unregistered.v1")

    def test_renderer_cannot_change_semantics(self):
        package = resolve_start_package()
        pin = pin_start_package_for_save(package)
        # Normal registry profiles are all semantic-safe.
        packet = make_reconstruction_packet(pin, "b" * 64, "axm.render.vector-bridge.v1")
        self.assertEqual(packet["bridge_archetype_id"], pin["bridge_archetype_id"])

    def test_command_pair_remains_visible(self):
        package = resolve_start_package()
        anchors = set(package["bridge_archetype"]["semantic_anchors"])
        self.assertIn("human_or_primary_explorer", anchors)
        self.assertIn("ai_or_secondary_collaborator", anchors)


if __name__ == "__main__":
    unittest.main()
