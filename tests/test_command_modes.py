import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from axm_star_sim.command import (
    COMMAND_MODES,
    append_discussion_message,
    crew_assessment,
    plan_command,
    proposal,
    resolve_collaboration,
)
from axm_star_sim.generator import generate_system
from axm_star_sim.io import append_runtime_event, load_ledger, load_pending_session, save_pending_session, write_system
from axm_star_sim.runtime import initial_runtime_state, resolve_turn, verify_recorded_event


class CommandModeTests(unittest.TestCase):
    def system(self):
        data = generate_system("AXM-FOUR-MODE-TEST").to_dict()
        data["active_command_mode"] = "autonomous_deterministic"
        return data

    def test_exactly_four_modes(self):
        self.assertEqual(set(COMMAND_MODES), {
            "autonomous_deterministic", "ai_command", "human_command", "collaborative_command"
        })
        self.assertEqual(sorted(m["number"] for m in COMMAND_MODES.values()), [1, 2, 3, 4])

    def test_crew_assessment_is_deterministic(self):
        system = self.system()
        state = initial_runtime_state(system)
        first = crew_assessment(system, state)
        second = crew_assessment(system, state)
        self.assertEqual(first, second)
        self.assertIn(first["recommended_action"], system["adventure"]["selected_opportunity"]["actions"])

    def test_mode_one_crew_has_authority(self):
        system = self.system()
        state = initial_runtime_state(system)
        plan = plan_command(system=system, state=state, mode="autonomous_deterministic")
        self.assertEqual(plan["status"], "resolved")
        self.assertEqual(plan["decision"]["authority"], "deterministic_crew")
        self.assertEqual(plan["decision"]["selected_action"], plan["decision"]["crew_assessment"]["recommended_action"])

    def test_autonomous_story_sequence_is_reproducible_and_not_stuck(self):
        def run_sequence():
            system = self.system()
            state = initial_runtime_state(system)
            sequence = []
            for _ in range(8):
                decision = plan_command(system=system, state=state, mode="autonomous_deterministic")["decision"]
                event, state = resolve_turn(
                    system=system,
                    state=state,
                    action=decision["selected_action"],
                    entropy_mode="deterministic",
                    command_decision=decision,
                )
                sequence.append((event["action"], event["outcome"]["id"]))
            return sequence

        first = run_sequence()
        second = run_sequence()
        self.assertEqual(first, second)
        self.assertGreater(len({action for action, _outcome in first}), 1)

    def test_mode_two_ai_command_is_preserved(self):
        system = self.system()
        state = initial_runtime_state(system)
        selected = system["adventure"]["selected_opportunity"]["actions"][1]
        plan = plan_command(
            system=system,
            state=state,
            mode="ai_command",
            ai_proposal=proposal("ai", selected, "AI mission calculation"),
        )
        self.assertEqual(plan["decision"]["selected_action"], selected)
        self.assertEqual(plan["decision"]["authority"], "ai_commander")

    def test_mode_three_human_command_is_preserved(self):
        system = self.system()
        state = initial_runtime_state(system)
        selected = system["adventure"]["selected_opportunity"]["actions"][2]
        plan = plan_command(
            system=system,
            state=state,
            mode="human_command",
            human_proposal=proposal("human", selected, "Mike chooses this direction"),
        )
        self.assertEqual(plan["decision"]["selected_action"], selected)
        self.assertEqual(plan["decision"]["authority"], "human_commander")

    def test_mode_four_matching_votes_resolve(self):
        system = self.system()
        state = initial_runtime_state(system)
        selected = system["adventure"]["selected_opportunity"]["actions"][0]
        plan = plan_command(
            system=system,
            state=state,
            mode="collaborative_command",
            human_proposal=proposal("human", selected, "human reason"),
            ai_proposal=proposal("ai", selected, "ai reason"),
        )
        self.assertEqual(plan["status"], "resolved")
        self.assertEqual(plan["decision"]["resolution_method"], "matching_votes")

    def test_mode_four_disagreement_opens_discussion_without_tiebreak(self):
        system = self.system()
        state = initial_runtime_state(system)
        actions = system["adventure"]["selected_opportunity"]["actions"]
        plan = plan_command(
            system=system,
            state=state,
            mode="collaborative_command",
            human_proposal=proposal("human", actions[0], "human reason"),
            ai_proposal=proposal("ai", actions[1], "ai reason"),
        )
        self.assertEqual(plan["status"], "discussion_required")
        self.assertNotIn("selected_action", plan["session"])
        self.assertIn("no automatic tie-break", plan["session"]["rule"].lower())

    def test_discussion_requires_matching_final_votes(self):
        system = self.system()
        state = initial_runtime_state(system)
        actions = system["adventure"]["selected_opportunity"]["actions"]
        session = plan_command(
            system=system,
            state=state,
            mode="collaborative_command",
            human_proposal=proposal("human", actions[0], "human reason"),
            ai_proposal=proposal("ai", actions[1], "ai reason"),
        )["session"]
        session = append_discussion_message(
            system=system, session=session, speaker="human", message="Could we reduce risk?", proposed_action=actions[2]
        )
        session = append_discussion_message(
            system=system, session=session, speaker="ai", message="I accept the lower-risk route.", proposed_action=actions[2]
        )
        decision = resolve_collaboration(
            system=system,
            state=state,
            session=session,
            human_final_action=actions[2],
            ai_final_action=actions[2],
            summary="Shared direction after risk discussion.",
        )
        self.assertEqual(decision["selected_action"], actions[2])
        self.assertEqual(decision["resolution_method"], "post_discussion_consensus")
        with self.assertRaises(ValueError):
            resolve_collaboration(
                system=system,
                state=state,
                session=session,
                human_final_action=actions[0],
                ai_final_action=actions[1],
            )

    def test_command_record_is_inside_replay_integrity(self):
        system = self.system()
        state = initial_runtime_state(system)
        decision = plan_command(system=system, state=state, mode="autonomous_deterministic")["decision"]
        event, _ = resolve_turn(
            system=system,
            state=state,
            action=decision["selected_action"],
            entropy_mode="deterministic",
            command_decision=decision,
        )
        check, _ = verify_recorded_event(system, state, event)
        self.assertTrue(check["valid"], check)
        event["command"]["authority"] = "silently_changed"
        check, _ = verify_recorded_event(system, state, event)
        self.assertFalse(check["valid"])

    def test_io_writes_command_console_and_pending_session(self):
        system = self.system()
        with TemporaryDirectory() as temp:
            output = Path(temp)
            write_system(output, system, "collaborative_command")
            self.assertTrue((output / "command_console.html").exists())
            state = json.loads((output / "runtime_state.json").read_text(encoding="utf-8"))
            actions = system["adventure"]["selected_opportunity"]["actions"]
            session = plan_command(
                system=json.loads((output / "system.json").read_text(encoding="utf-8")),
                state=state,
                mode="collaborative_command",
                human_proposal=proposal("human", actions[0]),
                ai_proposal=proposal("ai", actions[1]),
            )["session"]
            save_pending_session(output, session, state)
            self.assertEqual(load_pending_session(output)["session_id"], session["session_id"])
            html = (output / "command_console.html").read_text(encoding="utf-8")
            self.assertIn("No automatic tie-break", html)


if __name__ == "__main__":
    unittest.main()
