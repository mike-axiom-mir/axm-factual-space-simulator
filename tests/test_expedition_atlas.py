import copy
import json
import tempfile
import unittest
from pathlib import Path

from axm_star_sim.atlas import (
    AtlasError,
    append_catalog_revision,
    build_expedition_atlas,
    create_revisit_packet,
    import_normalized_catalog,
    load_landmark_catalog,
    propagate_icrs_linear,
    record_visit,
    register_system_location,
    revisit_options,
    validate_atlas_sources,
    verify_visit_chain,
)
from axm_star_sim.generator import generate_system
from axm_star_sim.io import append_runtime_event, write_system
from axm_star_sim.runtime import initial_runtime_state, resolve_turn


class ExpeditionAtlasTests(unittest.TestCase):
    def test_catalog_and_policy_validate(self):
        self.assertEqual(validate_atlas_sources(), [])
        catalog = load_landmark_catalog()
        self.assertEqual(catalog["coordinate_frame"], "ICRS")
        self.assertGreaterEqual(len(catalog["landmarks"]), 4)

    def test_real_landmarks_are_stable_across_master_seeds(self):
        first = build_expedition_atlas(generate_system("ATLAS-STABLE-A").to_dict(), created_at="2026-08-02T00:00:00Z")
        second = build_expedition_atlas(generate_system("ATLAS-STABLE-B").to_dict(), created_at="2026-08-02T00:00:00Z")
        for location_id in ("catalog:sol", "catalog:proxima-centauri", "catalog:trappist-1", "catalog:51-pegasi"):
            self.assertEqual(
                first["locations"][location_id]["authoritative_snapshot_sha256"],
                second["locations"][location_id]["authoritative_snapshot_sha256"],
            )
        self.assertNotEqual(first["active_location_id"], second["active_location_id"])

    def test_frontier_is_explicitly_not_a_catalog_claim(self):
        system = generate_system("ATLAS-FRONTIER").to_dict()
        atlas = build_expedition_atlas(system, created_at="2026-08-02T00:00:00Z")
        location = atlas["locations"][atlas["active_location_id"]]
        self.assertEqual(location["knowledge_class"], "procedural_frontier")
        self.assertEqual(location["coordinates"]["truth_type"], "simulation_prior")
        self.assertIn("not a claim", location["coordinates"]["warning"])

    def test_visit_chain_is_append_only_and_tamper_detectable(self):
        system = generate_system("ATLAS-VISIT").to_dict()
        atlas = build_expedition_atlas(system, created_at="2026-08-02T00:00:00Z")
        self.assertTrue(verify_visit_chain(atlas)["valid"])
        state = initial_runtime_state(system)
        action = state["action_menu"]["actions"][0]["action_id"]
        event, _updated = resolve_turn(system=system, state=state, action=action, entropy_mode="deterministic")
        atlas = record_visit(atlas, atlas["active_location_id"], event, visited_at="2026-08-02T00:01:00Z")
        self.assertTrue(verify_visit_chain(atlas)["valid"])
        damaged = copy.deepcopy(atlas)
        damaged["visits"][-1]["outcome"] = "rewritten"
        self.assertFalse(verify_visit_chain(damaged)["valid"])

    def test_revisit_packet_changes_render_not_history(self):
        atlas = build_expedition_atlas(generate_system("ATLAS-RENDER").to_dict(), created_at="2026-08-02T00:00:00Z")
        location_id = atlas["active_location_id"]
        original_visit_head = atlas["visit_chain_head"]
        original_location_hash = atlas["locations"][location_id]["authoritative_snapshot_sha256"]
        first, atlas = create_revisit_packet(
            atlas, location_id, "axm-vector-v0.7", "asset-fabric-v1", created_at="2026-08-02T00:10:00Z"
        )
        second, atlas = create_revisit_packet(
            atlas, location_id, "future-immersive-sim-v9", "asset-fabric-v8", created_at="2032-05-01T00:00:00Z"
        )
        self.assertNotEqual(first["packet_sha256"], second["packet_sha256"])
        self.assertEqual(first["authoritative_location_snapshot_sha256"], original_location_hash)
        self.assertEqual(second["authoritative_location_snapshot_sha256"], original_location_hash)
        self.assertEqual(atlas["visit_chain_head"], original_visit_head)
        self.assertEqual(len(atlas["locations"][location_id]["render_history"]), 2)

    def test_catalog_revision_does_not_rewrite_visits(self):
        atlas = build_expedition_atlas(generate_system("ATLAS-REVISION").to_dict(), created_at="2026-08-02T00:00:00Z")
        before_visits = copy.deepcopy(atlas["visits"])
        before_locations = {k: v["authoritative_snapshot_sha256"] for k, v in atlas["locations"].items()}
        atlas = append_catalog_revision(
            atlas,
            "gaia-future-release-snapshot",
            "ab" * 32,
            [{"old_location_id": "catalog:proxima-centauri", "method": "spatial_neighbourhood_review", "status": "candidate_match"}],
            created_at="2030-01-01T00:00:00Z",
        )
        self.assertEqual(atlas["visits"], before_visits)
        self.assertEqual({k: v["authoritative_snapshot_sha256"] for k, v in atlas["locations"].items()}, before_locations)
        self.assertFalse(atlas["catalog_revisions"][0]["historical_visits_rewritten"])

    def test_register_second_system_opens_route_and_revisit(self):
        first_system = generate_system("ATLAS-BRANCH-A").to_dict()
        second_system = generate_system("ATLAS-BRANCH-B").to_dict()
        atlas = build_expedition_atlas(first_system, created_at="2026-08-02T00:00:00Z")
        old_active = atlas["active_location_id"]
        atlas = register_system_location(atlas, second_system, make_active=True)
        atlas = record_visit(atlas, atlas["active_location_id"], None, "branch_arrival", visited_at="2026-08-02T01:00:00Z")
        self.assertNotEqual(old_active, atlas["active_location_id"])
        options = {item["location_id"]: item for item in revisit_options(atlas)}
        self.assertIn(old_active, options)
        self.assertIn(atlas["active_location_id"], options)
        self.assertEqual(atlas["routes"][-1]["feasibility"], "resolved_by_event_ledger_not_coordinate_map")

    def test_unvisited_catalog_anchor_cannot_be_reconstructed_as_visit(self):
        atlas = build_expedition_atlas(generate_system("ATLAS-UNVISITED").to_dict(), created_at="2026-08-02T00:00:00Z")
        with self.assertRaises(AtlasError):
            create_revisit_packet(atlas, "catalog:trappist-1", "visual-v1")

    def test_linear_propagation_is_display_only(self):
        proxima = next(x for x in load_landmark_catalog()["landmarks"] if x["location_id"] == "catalog:proxima-centauri")
        propagated = propagate_icrs_linear(proxima["coordinates"], 2030.0)
        self.assertEqual(propagated["navigation_authority"], "display_only")
        self.assertNotEqual(propagated["propagated_ra_deg"], proxima["coordinates"]["ra_deg"])

    def test_normalized_catalog_import_adds_revision_without_auto_merge(self):
        atlas = build_expedition_atlas(generate_system("ATLAS-IMPORT").to_dict(), created_at="2026-08-02T00:00:00Z")
        before_visits = copy.deepcopy(atlas["visits"])
        snapshot = {
            "schema": "axm.normalized-atlas-catalog.v1",
            "snapshot_id": "gaia-demo-release-1",
            "epoch": "J2000",
            "source_ids": ["simbad_cds_gaia_dr3"],
            "records": [{
                "external_id": "proxima-release-record",
                "name": "Proxima Centauri release record",
                "object_class": "stellar_system",
                "ra_deg": 217.4289422216058,
                "dec_deg": -62.67949018907555,
                "parallax_mas": 768.0665,
                "parallax_error_mas": 0.0499,
                "pmra_mas_yr": -3781.741,
                "pmdec_mas_yr": 769.465,
                "known_worlds": ["Proxima Centauri b"],
                "source_ids": ["nasa_exoplanet_catalog_proxima_b"],
            }],
        }
        atlas, report = import_normalized_catalog(atlas, snapshot)
        self.assertEqual(report["locations_imported"], 1)
        self.assertEqual(report["automatic_cross_release_merges"], 0)
        self.assertEqual(atlas["visits"], before_visits)
        imported = atlas["locations"]["catalog-import:gaia-demo-release-1:proxima-release-record"]
        self.assertEqual(imported["knowledge_class"], "catalog_incomplete")
        self.assertEqual(len(atlas["catalog_revisions"]), 1)

    def test_io_writes_and_updates_atlas(self):
        system = generate_system("ATLAS-IO").to_dict()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            manifest = write_system(output, system)
            self.assertIn("expedition_atlas.json", manifest["files"])
            self.assertTrue((output / "atlas.html").exists())
            atlas_before = json.loads((output / "expedition_atlas.json").read_text(encoding="utf-8"))
            state = json.loads((output / "runtime_state.json").read_text(encoding="utf-8"))
            action = state["action_menu"]["actions"][0]["action_id"]
            event, updated = resolve_turn(system=system, state=state, action=action, entropy_mode="deterministic")
            manifest = append_runtime_event(output, event, updated)
            atlas_after = json.loads((output / "expedition_atlas.json").read_text(encoding="utf-8"))
            self.assertEqual(len(atlas_after["visits"]), len(atlas_before["visits"]) + 1)
            self.assertIn("location_packet.json", manifest["files"])
            self.assertTrue(verify_visit_chain(atlas_after)["valid"])


if __name__ == "__main__":
    unittest.main()
