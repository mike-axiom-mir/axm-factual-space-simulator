import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from axm_star_sim.adventure_slots import (
    AdventureSlotError,
    act_in_adventure_slot,
    create_adventure_slot,
    export_player_bundle,
    forge_external_ai_assisted_scenario,
    forge_offline_base_scenario,
    list_adventure_slots,
    prepare_external_forge_request_data,
    validate_external_proposal,
    verify_adventure_slot,
)
from axm_star_sim.blind_forge import scan_public_bundle_for_private_leaks, verify_private_reveal
from axm_star_sim.generator import generate_system


class AdventureSlotTests(unittest.TestCase):
    def setUp(self):
        self.system = generate_system("AXM-V09-SLOT-WORLD").to_dict()
        self.request = prepare_external_forge_request_data(self.system, "AXM-V09-FORGE")
        first = self.request["candidate_shortlist"][0]
        self.proposal = {
            "schema": "axm.external-ai-forge-proposal.v1",
            "request_id": self.request["request_id"],
            "proposal_author": "Test reasoning seat",
            "preferred_anomaly_family_ids": [first["anomaly_family_id"]],
            "preferred_life_architecture_ids": [first["life_architecture_id"]],
            "emphasis_observable_ids": [],
            "investigation_emphasis": "falsification_first",
            "rationale_summary": ["Prefer a measurable candidate with strong alternative explanations."],
            "proposal_nonce": "TEST",
        }

    def test_offline_base_is_deterministic_and_private(self):
        a_private, a_public = forge_offline_base_scenario(self.system, "OFFLINE-SEED")
        b_private, b_public = forge_offline_base_scenario(self.system, "OFFLINE-SEED")
        self.assertEqual(a_public["private_scenario_commitment_sha256"], b_public["private_scenario_commitment_sha256"])
        self.assertEqual(scan_public_bundle_for_private_leaks(a_public, a_private), [])
        self.assertTrue(verify_private_reveal(a_private, a_public)["valid"])
        self.assertEqual(a_public["adventure_slot_start"]["forge_mode"], "offline_base")
        self.assertFalse(a_public["adventure_slot_start"]["external_connection_required_after_creation"])

    def test_external_proposal_is_optional_and_locally_sealed(self):
        private, public = forge_external_ai_assisted_scenario(self.system, "AXM-V09-FORGE", self.proposal)
        self.assertTrue(verify_private_reveal(private, public)["valid"])
        self.assertEqual(public["adventure_slot_start"]["forge_mode"], "external_ai_assisted")
        self.assertFalse(public["adventure_slot_start"]["external_connection_required_after_creation"])
        self.assertEqual(private["forge_input_receipt"]["external_ai_role"], "proposal only")

    def test_external_ai_cannot_choose_hidden_truth(self):
        bad = copy.deepcopy(self.proposal)
        bad["origin_class"] = "candidate_living_system"
        with self.assertRaises(AdventureSlotError):
            validate_external_proposal(bad, self.request)

    def test_external_request_is_safe_and_has_no_selected_truth(self):
        serialized = json.dumps(self.request)
        self.assertNotIn("private_simulation_truth", serialized)
        self.assertNotIn("resolution_secret", serialized)
        self.assertNotIn("selected_candidate_id", serialized)
        self.assertGreaterEqual(len(self.request["candidate_shortlist"]), 4)

    def test_create_act_verify_offline_slot(self):
        with tempfile.TemporaryDirectory() as temp:
            slots = Path(temp)
            created = create_adventure_slot(
                slots, "slot-one", "Offline One", "WORLD-A", "FORGE-A", "offline_base"
            )
            self.assertTrue(created["slot_console"].exists())
            act_in_adventure_slot(slots, "slot-one", "broad_spectrum_survey", "TOKEN-1")
            verification = verify_adventure_slot(slots, "slot-one")
            self.assertTrue(verification["valid"], verification)
            self.assertEqual(verification["events"], 1)

    def test_create_external_slot_and_continue_without_proposal(self):
        with tempfile.TemporaryDirectory() as temp:
            slots = Path(temp)
            created = create_adventure_slot(
                slots,
                "external",
                "External Start",
                "AXM-V09-SLOT-WORLD",
                "AXM-V09-FORGE",
                "external_ai_assisted",
                proposal=self.proposal,
            )
            self.assertFalse(created["metadata"]["external_connection_required_after_creation"])
            act_in_adventure_slot(slots, "external", "repeat_changed_geometry", "TOKEN-X")
            self.assertTrue(verify_adventure_slot(slots, "external")["valid"])

    def test_manifest_detects_tamper(self):
        with tempfile.TemporaryDirectory() as temp:
            slots = Path(temp)
            create_adventure_slot(slots, "tamper", "Tamper", "W", "F")
            target = slots / "tamper" / "session" / "player_public" / "PLAYER_HANDOFF.txt"
            target.write_text(target.read_text(encoding="utf-8") + "\nTAMPER", encoding="utf-8")
            self.assertFalse(verify_adventure_slot(slots, "tamper")["valid"])

    def test_player_export_contains_no_private_paths_or_values(self):
        with tempfile.TemporaryDirectory() as temp:
            slots = Path(temp)
            create_adventure_slot(slots, "export", "Export", "W2", "F2")
            path = export_player_bundle(slots, "export")
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                text = "\n".join(
                    archive.read(name).decode("utf-8", errors="ignore")
                    for name in names
                    if name.endswith((".json", ".jsonl", ".txt", ".html"))
                )
            self.assertFalse(any("private" in name.lower() for name in names))
            self.assertNotIn("resolution_secret", text)
            self.assertNotIn("private_simulation_truth", text)

    def test_list_slots_reads_multiple_saves(self):
        with tempfile.TemporaryDirectory() as temp:
            slots = Path(temp)
            create_adventure_slot(slots, "a", "A", "WA", "FA")
            create_adventure_slot(slots, "b", "B", "WB", "FB")
            self.assertEqual([row["slot_id"] for row in list_adventure_slots(slots)], ["a", "b"])

    def test_slot_path_is_confined_to_slots_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            slots = root / "slots"
            created = create_adventure_slot(slots, "../../escape", "Safe", "W", "F")
            self.assertEqual(created["slot_dir"].parent, slots.resolve())
            self.assertFalse((root.parent / "escape").exists())

    def test_slot_symlink_escape_is_rejected_before_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            slots = root / "slots"
            outside = root / "outside"
            slots.mkdir()
            outside.mkdir()
            link = slots / "linked"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")
            with self.assertRaises(AdventureSlotError):
                create_adventure_slot(slots, "linked", "Linked", "W", "F", overwrite=True)
            self.assertTrue(outside.exists())

    def test_wrong_request_id_fails(self):
        bad = copy.deepcopy(self.proposal)
        bad["request_id"] = "WRONG"
        with self.assertRaises(AdventureSlotError):
            validate_external_proposal(bad, self.request)


if __name__ == "__main__":
    unittest.main()
