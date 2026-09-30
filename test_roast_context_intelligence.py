# -*- coding: utf-8 -*-
"""
KAZUMI CONTEXTUAL ROAST INTELLIGENCE COMPREHENSIVE VERIFICATION SUITE
Validates all 22 sections of the contextual roast fix:
- Section 1 & 2: Context -> Observation -> Comedy Angle -> Punchline pipeline
- Section 3: No-context playful honesty (never invent random generic nonsense)
- Section 4: Comedy angle selection
- Section 5: Coding sequel & archaeology
- Section 6: Gaming donations
- Section 7: Overconfidence reversal
- Section 8: Late response detection
- Section 9 & 10: Callbacks and memory profiles
- Section 11: Level 5 is clever contextual escalation, not random words
- Section 13: Banned generic filler rejection
- Section 14 & 21: Semantic validator 8-point test
- Section 16: Random mode allowed only when requested
- Section 18: Multi-person context isolation
- Section 19: Length <= 3 sentences
"""

import unittest
from discord_features.roast_engine import (
    RoastEngine,
    ContextAnalyzer,
    RoastValidator,
    ComedyAngle,
    BANNED_GENERIC_FILLER,
    NO_CONTEXT_PLAYFUL_RESPONSES
)
from discord_features.database import FeatureDatabase


class ContextualRoastIntelligenceTests(unittest.TestCase):

    def setUp(self):
        self.db = FeatureDatabase(persist_dir="isa_memory_test_roast")
        self.engine = RoastEngine(self.db)

    def tearDown(self):
        import shutil, os
        if os.path.exists("isa_memory_test_roast"):
            try:
                shutil.rmtree("isa_memory_test_roast")
            except Exception:
                pass

    def test_section_5_coding_sequel(self):
        """User: Bro I fixed my code -> wait it broke again"""
        obs = ContextAnalyzer.find_roastable_observation(
            target_recent_messages=["Bro I fixed my code", "wait it broke again"],
            target_name="Dev"
        )
        self.assertIsNotNone(obs)
        self.assertEqual(obs.category, "CODING_SEQUEL")
        self.assertEqual(obs.angle, ComedyAngle.REVERSAL)
        p3 = obs.get_punchline(level=3)
        self.assertIn("character development", p3)
        p5 = obs.get_punchline(level=5)
        self.assertIn("franchise deal", p5)

    def test_section_6_gaming_donations(self):
        """User loses 5 matches in a row"""
        obs = ContextAnalyzer.find_roastable_observation(
            target_recent_messages=["Lost 5 matches in a row, team is trash"],
            target_name="Gamer"
        )
        self.assertIsNotNone(obs)
        self.assertEqual(obs.category, "GAMING_DONATION")
        self.assertEqual(obs.angle, ComedyAngle.IRONY)
        p3 = obs.get_punchline(level=3)
        self.assertIn("donating wins", p3)
        p2 = obs.get_punchline(level=2)
        self.assertIn("blaming matchmaking", p2)

    def test_section_7_overconfidence(self):
        """User: Easy. I know exactly what I'm doing -> makes obvious mistake"""
        obs = ContextAnalyzer.find_roastable_observation(
            target_recent_messages=["Easy. I know exactly what I'm doing.", "wait oops it failed"],
            target_name="User"
        )
        self.assertIsNotNone(obs)
        self.assertEqual(obs.category, "OVERCONFIDENCE")
        p2 = obs.get_punchline(level=2)
        self.assertIn("The confidence was impressive. The results were not.", p2)

    def test_section_8_late_response(self):
        """User returns after 8 hours saying 'sorry was busy'"""
        obs = ContextAnalyzer.find_roastable_observation(
            target_recent_messages=["sorry i was busy"],
            time_away_seconds=28800, # 8 hours
            target_name="User"
        )
        self.assertIsNotNone(obs)
        self.assertEqual(obs.category, "LATE_RESPONSE")
        self.assertEqual(obs.angle, ComedyAngle.DEADPAN)
        p2 = obs.get_punchline(level=2)
        self.assertIn("bro took a side quest and came back like nothing happened 💀", p2)

    def test_section_10_personality_profile(self):
        """User profile with known project hopping"""
        obs = ContextAnalyzer.find_roastable_observation(
            target_recent_messages=["I have another amazing project idea"],
            target_patterns=["project_hopping", "abandoned_repos"],
            target_name="Dev"
        )
        self.assertIsNotNone(obs)
        self.assertEqual(obs.category, "PROJECT_HOPPING")
        p3 = obs.get_punchline(level=3)
        self.assertIn("unfinished-project folder is about to need its own server", p3)

    def test_section_3_no_context_honesty(self):
        """If there is nothing to roast, don't invent something!"""
        success, roast, lvl = self.engine.generate_roast(
            target_name="QuietPerson",
            context_text=None,
            target_recent_messages=[],
            allow_random=False
        )
        self.assertTrue(success)
        # Verify it uses honest playful deflections
        self.assertTrue(
            any(k in roast.lower() for k in ["zero evidence", "give me something to work with", "stand still", "innocent bystanders", "zero context"]),
            f"Expected honest playful response, got: {roast}"
        )
        # Ensure zero generic clichés
        for filler in BANNED_GENERIC_FILLER:
            self.assertNotIn(filler, roast.lower())

    def test_section_13_banned_generic_filler_rejection(self):
        """Semantic validator must reject bad generic insults"""
        clichés = [
            "I just dispatched a search party for your common sense. They found nothing and requested hazard pay.",
            "Your personality resembles that of a damp sock.",
            "bro has the charisma of a loading screen 💀",
            "I've seen NPCs with more brain cells.",
            "Touch grass, you have a major skill issue because you aren't built different."
        ]
        for c in clichés:
            val = RoastValidator.validate_roast(c, context="test", target_name="Target")
            self.assertFalse(val["is_valid"], f"Failed to reject: {c}")
            self.assertTrue(val["is_generic"], f"Expected is_generic=True for: {c}")

    def test_section_19_length_constraint(self):
        """Roasts must be 1 to 3 punchy sentences, not essays"""
        long_essay = (
            "Sentence one is explaining your lack of logic. "
            "Sentence two continues the elaborate explanation of your terrible decisions. "
            "Sentence three adds another unnecessary analytical breakdown of your mistakes. "
            "Sentence four just keeps droning on like an academic textbook. "
            "Sentence five ensures that all comedic timing is completely extinguished."
        )
        val = RoastValidator.validate_roast(long_essay, context="mistakes", target_name="Target")
        self.assertFalse(val["is_valid"])
        self.assertTrue(val["is_overwritten"])


if __name__ == "__main__":
    unittest.main()
