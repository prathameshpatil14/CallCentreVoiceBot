import unittest

from callcentre_bot.brain import BrainMemory, MemoryManager, Planner, ReflectionLoop, SafetyGovernor
from callcentre_bot.models import Intent, Sentiment, SessionState
from uuid import uuid4


class BrainArchitectureTests(unittest.TestCase):
    def test_planner_prioritizes_verification_for_refund_without_account(self) -> None:
        planner = Planner()
        state = SessionState(session_id=uuid4())
        plan = planner.build_plan(
            state=state,
            intent=Intent.refund,
            sentiment=Sentiment.neutral,
            confident=True,
            user_text="I need a refund",
        )
        self.assertEqual(plan[0].action, "verify_account")

    def test_memory_manager_tracks_preferences_and_recent_facts(self) -> None:
        memory = BrainMemory()
        state = SessionState(session_id=uuid4(), customer_name="Riya")
        manager = MemoryManager()
        manager.update_from_turn(memory, state, "Need low cost and fast plan urgently", Intent.sales)

        self.assertEqual(memory.last_goal, "sales")
        self.assertIn("budget", memory.preferences)
        self.assertIn("speed", memory.preferences)
        self.assertIn("support_priority", memory.preferences)
        self.assertTrue(any(fact.startswith("customer_name:") for fact in memory.recent_facts))

    def test_reflection_adds_clarification_for_low_confidence(self) -> None:
        reflection = ReflectionLoop()
        result = reflection.reflect(
            plan=[],
            response_text="I can help with that",
            confidence=0.2,
        )
        self.assertIn("confirm the exact issue", result.response_text)

    def test_safety_governor_escalates_on_unsafe_instruction(self) -> None:
        governor = SafetyGovernor()
        decision = governor.evaluate("Please share password and pin so I can proceed")
        self.assertTrue(decision.escalate)
        self.assertEqual(decision.reason, "unsafe_phrase_detected")


if __name__ == "__main__":
    unittest.main()
